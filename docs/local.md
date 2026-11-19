# Local development

## Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build --wait --wait-timeout 180
```

Open [localhost:5173](http://localhost:5173). API docs: [localhost:8000/docs](http://localhost:8000/docs).

Compose starts PostgreSQL, runs migration once, then starts the API and frontend. Clicks and daily statistics are handled directly by FastAPI/PostgreSQL. No queue or background process is required.

If Docker is only available in WSL:

```powershell
wsl -e sh -lc 'cd /mnt/d/MT/CutLink && docker compose up -d --build --wait --wait-timeout 180'
```

```powershell
docker compose logs -f api
docker compose run --rm migrate
docker compose down
```

`down` keeps the PostgreSQL volume. `down -v` deletes local database data; use it only for an intentional reset.

## Host venv + pip

```powershell
docker compose up -d db
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Settings read `../.env`, then `.env`; process environment overrides both. Local HTTP uses `COOKIE_SECURE=false`. AWS uses Secure cookies. Set a secret of at least 32 characters and exact allowed origins before exposing the app outside localhost.

## Another PostgreSQL server

The backend is not tied to RDS. For host development, set `DATABASE_URL` to the new PostgreSQL endpoint and run the same migration command. Include the provider's required SSL settings, e.g. `?sslmode=require`.

Migration prepares table structure; it does not transfer existing users/links/clicks. Use PostgreSQL backup/restore to transfer data. Compose injects its local DB URL and the bundled AWS template injects RDS settings; change those runtime settings too when deploying with an external database.

## Tests

```powershell
docker compose up -d db
docker compose exec db createdb -U cutlink cutlink_test
docker compose --profile test run --build --rm test
```

Create `cutlink_test` only once. Tests reset only this disposable database, and refuse a database name without the `_test` suffix. For host tests, run `.\.venv\Scripts\python.exe -m pytest -q` inside backend. Set `TEST_DATABASE_URL` if using different test credentials.

From the root:

```powershell
python -m unittest discover -s scripts/tests -v
pwsh -File scripts/smoke.ps1 -BaseUrl http://localhost:5173
python scripts/check_outages.py --base-url http://localhost:5173 --wsl
```

Omit `--wsl` when Docker is directly on PATH. The outage check stops and restores only the local DB. Smoke checks leave a test account and remove their test links.

Frontend tests/build run from frontend: `npm run test:run` and `npm run build`.

References: [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
