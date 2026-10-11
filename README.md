# PipeSmith / P-113

This repository is the deployment source of truth for the existing Agent pipeline:

- `frontend/`: Next.js, deployed on Vercel.
- `backend/`: FastAPI and the existing Agent pipeline, deployed on Render.
- `.github/workflows/`: current CI workflows.

Authentication adds PostgreSQL for accounts, server-side sessions, and the admin audit log. Run Store, LangGraph checkpoints, Error Book, workspaces, artifacts, source files, and DuckDB sandbox keep their existing storage paths and formats. The Agent runner and review policy remain the deployment baseline.

## Run locally

Install the backend requirements from `backend/`, copy `backend/.env.example` to `.env`, then start FastAPI:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Authentication requires `DATABASE_URL` and a `SESSION_SECRET` of at least 32 characters; without them the app fails closed. Run the auth migration manually against a dedicated database, then create an initial Admin using `python -m src.cli users create --username quantri --name "Quản trị" --role admin`. The CLI reads the password without echoing it.

Start the frontend in a second terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Local frontend requests use `NEXT_PUBLIC_API_URL=http://localhost:8000`. The backend example config allows that origin in development.

## Deploy

Keep the current Vercel + Render structure and existing Agent/LLM variables. On Render, set the application PostgreSQL URL, `APP_ENV=production`, `SESSION_SECRET`, `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_SAMESITE=lax`, and the exact Vercel origin in `CORS_ORIGINS`. Run Alembic manually with a separate `MIGRATION_DATABASE_URL` only after a backup and explicit deployment approval; the backend does not auto-migrate.

On Vercel, set `BACKEND_URL` to the Render origin and `NEXT_PUBLIC_API_URL=/` before build. Browser requests then use `/api/v1/*` on the Vercel origin and Next.js rewrites proxy them to Render. Do not put backend secrets in frontend variables.

See [backend/docs/deploy-auth.md](backend/docs/deploy-auth.md) for PostgreSQL roles, migrations, staging checks, Vercel proxy limits, Render filesystem persistence, and rollback steps.

## CI

`.github/workflows/ci.yml` runs Ruff and pytest from `backend/`, frontend lint/format/typecheck/build, then builds both Docker images without pushing or deploying.
