# Cutlink

Small links. Big possibilities.

A URL shortener with email/password accounts, private link management, public 302 redirects, and click statistics. React + Vite + TypeScript + Bootstrap on the frontend; synchronous FastAPI + SQLAlchemy + PostgreSQL + Alembic on the backend. Redis handles the short-lived cache and Celery broker; a solo worker records events and one Beat process rolls them up every minute.

## Run locally with Compose

Prerequisites: Docker Engine + Docker Compose v2 or newer. On Windows, enable Docker Desktop's WSL integration or run Docker commands inside your Docker-enabled WSL distribution.

```powershell
Copy-Item .env.example .env
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

Open [localhost:5173](http://localhost:5173). Register an account, create a link, copy it, and open it in a new tab. API docs are at [localhost:8000/docs](http://localhost:8000/docs).

From Windows with a Docker daemon only accessible in WSL:

```powershell
wsl -e sh -lc 'cd /mnt/d/MT/CutLink && docker compose up -d --build --wait --wait-timeout 180'
```

Compose starts PostgreSQL and Redis, waits for PostgreSQL, runs the `migrate` one-shot container, and starts the API, worker and Beat only after migration succeeds. The frontend proxies `/api` and `/r` to the API, so browser cookies remain on the frontend origin. Frontend source files are mounted read-only for local editing and Vite refresh; rebuild when dependencies change. PostgreSQL data persists in the `postgres` volume. Redis is intentionally ephemeral. The optional `test` service is excluded from normal startup.

```powershell
docker compose logs -f api worker beat
docker compose run --rm migrate  # safe to repeat
docker compose down            # retains database volume
# Destructive local reset, only when you intend to delete all local data:
docker compose down -v
```

The default `.env` values are for localhost only. `JWT_SECRET` must be at least 32 characters. AWS injects a generated secret and sets `COOKIE_SECURE=true`. `ALLOWED_ORIGINS` is a JSON list of exact origins with no trailing slash. Mutating HTTP requests, including scripted requests, must send an allowed `Origin` header. URLs must use HTTP or HTTPS. Passwords must contain 10–128 characters.

When creating a link, the domain and `/r/` prefix are fixed to the app's current origin. Enter an optional custom ending such as `my-portfolio` to share `http://localhost:5173/r/my-portfolio`. Leave it blank for a random eight-character code. Custom endings are case-sensitive, use 3–64 letters, numbers, hyphens or underscores, and start with a letter or number. An ending already used by any account returns `409` instead of being silently replaced. Short codes stay fixed when editing a link.

Destination validation runs on both create and edit, in the browser and API: a full HTTP/HTTPS URL with a valid host/port is required, credentials and control characters are rejected, and the normalized URL must fit the database length. This checks URL structure; it does not guarantee the destination website is currently online.

## Python venv + pip development

Use Python 3.12 or newer. No uv installation is needed.

```powershell
docker compose up -d db redis
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The settings loader reads `../.env` and `.env`, with process environment variables taking precedence. In two additional terminals from `backend`:

```powershell
.\.venv\Scripts\celery.exe -A app.tasks:celery worker --pool=solo --concurrency=1 --loglevel=INFO
.\.venv\Scripts\celery.exe -A app.tasks:celery beat --loglevel=INFO --schedule=../.deploy/celerybeat-schedule
```

Create `.deploy` first if running Beat on the host. For the frontend in a separate terminal:

```powershell
cd frontend
npm ci
npm run dev
```

## Verification

The integration suite uses a real disposable PostgreSQL database named `cutlink_test` and real Redis. It refuses to reset a database whose name does not end in `_test`. Do not point `TEST_DATABASE_URL` at production. Fixtures drop the test schema, apply Alembic twice, then isolate each test with a truncate.

```powershell
docker compose up -d db redis
docker compose exec db createdb -U cutlink cutlink_test  # once; already exists is harmless
# Linux container tests, including on Windows/WSL:
docker compose --profile test run --build --rm test
# Or use the host venv:
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app migrations tests
cd ../frontend
npm run build
cd ..
pwsh -File scripts/smoke.ps1 -BaseUrl http://localhost:5173
```

`scripts/test-local.ps1 -Build` starts Compose, creates the test database if absent, runs pytest using the Windows venv, and performs the HTTP smoke checks. If Docker is only available in WSL, use the individual WSL Docker commands above instead.

Covered behaviors: registration and duplicate emails, login/logout and expired JWTs, cookie flags, Origin rejection, owner isolation on every link endpoint, CRUD and cache invalidation, URL validation, code collision retry, Redis/publisher failure fallback, bounded failed publish, event deduplication, repeatable UTC rollups, and liveness/readiness recovery. The smoke script checks the actual browser origin, cookie round trip, CRUD/redirect behavior, no-store headers, API 404s and SPA refresh. Each smoke run leaves a uniquely named test account and deletes its links.

To exercise real dependency outages with the stack running, keep a known enabled short code and run:

```powershell
docker compose stop redis
curl.exe -i http://localhost:5173/r/YOURCODE
# Expect 302 from PostgreSQL even when cache and broker are unavailable.
docker compose start redis
docker compose stop db
curl.exe -i http://localhost:5173/api/health/live   # 200
curl.exe -i http://localhost:5173/api/health/ready  # 503, bounded timeout
docker compose start db
# Once PostgreSQL is healthy, /ready returns 200 again.
```

Automated equivalents (run sequentially on your local test stack):

```powershell
python scripts/check_background.py --base-url http://localhost:5173
python scripts/check_outages.py --base-url http://localhost:5173 --wsl  # omit --wsl when Docker is on PATH
```

`check_background.py` waits up to 85 seconds for the real worker and Beat. `check_outages.py` temporarily stops Redis and PostgreSQL and restores them in a `finally` block. `check_migration_gate.py` temporarily stops the app, forces an invalid Alembic revision, asserts the API cannot start, then restores the normal stack. Run that script inside WSL if your Docker daemon is only available there. These scripts create disposable test accounts and remove the links they create.

## AWS architecture

```text
Browser --HTTPS--> CloudFront
                    |-- frontend --> private S3 (OAC + versioning)
                    |-- /api/*, /r/* --> ALB --HTTP--> Fargate
                                                         |-- API
                                                         |-- Redis (localhost)
                                                         |-- Celery worker (solo)
                                                         |-- Celery Beat
                                                         +--> private PostgreSQL RDS
```

`infra/base.yaml` provisions two public and two private subnets in two AZs, an internet gateway, one NAT gateway, an ALB, an ECS cluster, an encrypted PostgreSQL 17 RDS instance (`db.t4g.micro`, Single-AZ, 20 GB), generated Secrets Manager secrets, minimal execution/task roles, CloudWatch log group, versioned private S3 bucket and CloudFront distribution. `infra/app.yaml` provisions the four-container Fargate task (0.25 vCPU / 1 GB, one task, no public IP), service, and an independent migration task with the same backend image, private subnets, security group and database secrets.

Only the ALB can reach ECS port 8000, and only the ECS security group can reach RDS port 5432. Redis has no external port mapping. The ALB listener returns 403 unless CloudFront's secret origin header matches. Browser-to-CloudFront uses HTTPS; CloudFront-to-ALB uses HTTP in this demo. The execution role can read only the database and JWT secrets and write the application's logs; the application task role has no AWS permissions.

API and redirect behaviors have zero cache TTL and forward cookies, query strings and Origin/content-type headers. Error caching minimum TTL is also zero; error status codes and bodies stay unchanged. API methods include POST/PATCH/DELETE. A CloudFront Function rewrites only frontend navigation paths to `/index.html`; API and redirect errors retain their HTTP status. Static caching has `MinTTL: 0` to respect `index.html`'s `no-cache`, while hashed assets use one-year immutable cache headers. There are no distribution-wide error-page rewrites.

ECS checks `/api/health/live`; the ALB checks `/api/health/ready` every 30 seconds with a 120-second startup grace period. Readiness creates a separate PostgreSQL connection with a two-second connection timeout and two-second statement timeout, executes `SELECT 1`, and closes it. Redis failures are logged and do not fail readiness. Redis/worker/Beat are nonessential containers so background failure does not stop healthy SQL-backed redirects; inspect their CloudWatch streams and replace the task if a background process exits.

This is one demo environment with deliberate deployment downtime. NAT, ALB, Fargate, RDS, CloudFront and storage incur AWS charges. Nothing in local setup creates AWS resources.

## Manual AWS deployment

Requires PowerShell 7, AWS CLI v2 with a configured profile, Docker with buildx, Node 22+, npm, Git, and GHCR login. Choose an AWS region with at least two AZs and the specified RDS instance class. Commit the source before deploying, because image tags use the commit SHA.

Authenticate Docker to GHCR using your credential manager or `docker login ghcr.io` with a GitHub token that can write packages. **Make the backend package public** in GitHub package settings; ECS pulls it without registry credentials. The deploy script checks anonymous access and stops if it is private. Backend deployment is manual. GitHub Actions can publish its image and upload frontend builds to S3 after successful CI on `main`; see [publication setup](docs/github-actions.md).

```powershell
pwsh -File scripts/deploy.ps1 `
  -ProjectName cutlink `
  -Region ap-southeast-1 `
  -Profile YOUR_PROFILE `
  -ImageRepository ghcr.io/phanmanhtan/cutlink
```

The script validates templates and builds the frontend, deploys the base stack, pushes the Linux AMD64 backend with the commit-SHA tag, reads its immutable registry digest, saves the previous backend digest and S3 index version under ignored `.deploy/`, stops the old service, and deploys the new app stack with desired count **0**. It runs the migration as a separate ECS task and checks the container's exit code. Only exit code 0 permits desired count **1**. It waits for ECS stability and an ALB healthy target, uploads hashed assets first and `index.html` last, invalidates `/index.html`, then runs smoke checks through CloudFront.

Migration failure leaves the service stopped. Failed checks throw immediately; inspect logs and choose whether to retry or roll back. Changes to the schema must remain compatible with the previous release. Application rollback never downgrades the database. The script holds a local file lock to prevent concurrent runs on one machine; operators must serialize deployments across machines too. ECS maximum percent 100 / minimum healthy percent 0 and explicit stopping avoid overlapping releases and duplicate Beat processes. Do not run a separate service update manually alongside the script.

## Logs, metrics and rollback

```powershell
aws logs tail /ecs/cutlink --follow --region ap-southeast-1 --profile YOUR_PROFILE
aws cloudformation describe-stack-events --stack-name cutlink-app --region ap-southeast-1 --profile YOUR_PROFILE
pwsh -File scripts/rollback.ps1 -Profile YOUR_PROFILE
```

Rollback reads `.deploy/previous-release.json`, stops the current task, redeploys the previous backend digest, restores the saved version of `index.html`, invalidates the index, and runs smoke checks. Old hashed assets are kept in S3. Retain your `.deploy` release records securely; they contain infrastructure IDs and release metadata, not credentials. For a failed first deployment there is no previous release: fix the migration/image and rerun.

Inspect CloudWatch logs for `api`, `redis`, `worker`, `beat`, and `migration`. Use standard RDS CloudWatch metrics (`DatabaseConnections`, `CPUUtilization`, `FreeStorageSpace`) alongside ALB target health and ECS memory/CPU. This demo does not provision alarms or extra monitoring services.

## Teardown

Delete the app stack first because it imports base outputs:

```powershell
aws cloudformation delete-stack --stack-name cutlink-app --region ap-southeast-1 --profile YOUR_PROFILE
aws cloudformation wait stack-delete-complete --stack-name cutlink-app --region ap-southeast-1 --profile YOUR_PROFILE
aws cloudformation delete-stack --stack-name cutlink-base --region ap-southeast-1 --profile YOUR_PROFILE
aws cloudformation wait stack-delete-complete --stack-name cutlink-base --region ap-southeast-1 --profile YOUR_PROFILE
```

The base stack takes a final RDS snapshot and retains the frontend bucket and log group. Record the bucket name and snapshot ID before deleting the stack. Retained S3 object versions, logs and snapshots still incur storage charges; remove them manually only after deciding they are no longer needed. Never empty a retained bucket as part of routine deploy or rollback.

## Scope and tradeoffs

- Codes can be random (eight characters) or custom (3–64 characters), with a shared database uniqueness constraint. Random collisions retry; duplicate custom endings return `409`. Migration `0002` widens the column without changing existing links.
- Sessions are eight-hour HS256 JWTs in HttpOnly, SameSite=Lax cookies (Secure on AWS). Logout clears the browser cookie; there is no token revocation table, password reset, email verification or refresh token flow in this version.
- Redirects are direct HTTP 302 with `Cache-Control: no-store`. Cache entries live for 30 seconds; updates/deletes invalidate after commit. If invalidation fails or races another request, an old destination can remain visible for up to the cache TTL.
- Publishing uses short Redis socket deadlines and no request-side publish retry. Failed publishes do not block redirects. Click UUIDs deduplicate worker retries. Rollups upsert absolute UTC daily counts under a transaction advisory lock, so repeated runs do not add counts twice.
- Daily charts show the last 30 UTC days from the rollup table and refresh about once per minute; total clicks count processed events. Redis and queued events are ephemeral and may be lost on task replacement. Processed clicks, users and links persist in RDS.
- One tiny Fargate task and Single-AZ RDS favor a small demo. This setup accepts downtime and has no horizontal scaling or high availability. Search filters the current 20-link page and pagination covers the full account.

## Project layout

```text
frontend/   React UI, Bootstrap styles, Vite proxy, Dockerfile
backend/    FastAPI modules, Celery tasks, Alembic migrations, PostgreSQL tests, Dockerfile
infra/      CloudFormation base and app templates
scripts/    PowerShell deploy, rollback, smoke and local-test commands
compose.yaml
.env.example
```

## GitHub Actions

`.github/workflows/ci.yml` runs on branch pushes, pull requests, and manual dispatch. No AWS or GHCR credentials are required for CI tests.

- Backend jobs create a pip venv on Python 3.12 and 3.14, check dependencies and Python style, and run the integration suite against PostgreSQL 17 and Redis 7 service containers. Migration fixtures apply the initial schema twice on an empty database.
- The frontend job runs `npm ci` and the TypeScript/production build, then uploads `frontend-dist` for review.
- The infrastructure job checks both CloudFormation templates and parses all PowerShell scripts.
- The Compose job builds real images, forces a migration failure and asserts that the API never starts, starts the full stack, runs HTTP smoke checks, waits for a real worker and Beat to process exactly one click, and stops Redis/PostgreSQL to verify fallback and recovery. Container logs are uploaded on failure.

After all checks pass on a `main` push, CD publishes the backend image to GHCR and uploads the tested frontend build to S3. It does not deploy the backend or run migrations. Feature branches and PRs only test. For a manual main release use **Actions → CI / CD → Run workflow** and enable `publish_release`; leave it off for tests only. Set the CI jobs as required checks in branch protection if desired. Configure the production environment using [docs/github-actions.md](docs/github-actions.md). No AWS resources are provisioned by this workflow.
