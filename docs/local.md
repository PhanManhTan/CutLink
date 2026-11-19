# Local development

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

Use Python 3.12 or newer with venv and pip.

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


Frontend: run npm run test:run from frontend/. Release gates: python -m unittest discover -s scripts/tests -v from root.

References: [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
