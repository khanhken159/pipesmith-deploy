# PipeSmith / P-113 — deploy copy

This is a clean, standalone deployment copy of PipeSmith. The source is split into two applications:

- frontend/: Next.js, deployed on Vercel with Root Directory = frontend.
- backend/: FastAPI and the Agent/pipeline code, deployed on Render with Root Directory = backend.

This copy does not include the old Git history. Do not commit a .env file; use the .env.example files as templates.

## Run locally

Terminal 1 — backend:

    cd backend
    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    # PowerShell
    Copy-Item .env.example .env
    # macOS/Linux
    cp .env.example .env
    python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

Terminal 2 — frontend:

    cd frontend
    npm ci
    # PowerShell
    Copy-Item .env.example .env.local
    # macOS/Linux
    cp .env.example .env.local
    npm run dev

The frontend defaults to http://localhost:8000; change the API URL with NEXT_PUBLIC_API_URL.

## Deploy the backend on Render

Create a Web Service from the new repository:

- Root Directory: backend
- Runtime: Docker (uses backend/Dockerfile) or Python
- Python Build Command: pip install -r requirements.txt
- Python Start Command: python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT
- Health check path: /health

Set these environment variables on Render:

    APP_ENV=production
    LLM_PROVIDER=mock
    CORS_ORIGINS=https://<frontend>.vercel.app

If using a real LLM provider, set OPENAI_API_KEY on Render only. Never put it in the frontend, Git, or CI.

## Deploy the frontend on Vercel

Import the same new repository:

- Root Directory: frontend
- Framework: Next.js
- Build Command: npm run build
- Output Directory: leave the default blank

Set this environment variable:

    NEXT_PUBLIC_API_URL=https://<backend>.onrender.com

After Vercel gives you a domain, set CORS_ORIGINS on Render to that exact origin.

## CI

.github/workflows/ci.yml runs Ruff and pytest from backend/, and runs the Next.js lint, format, typecheck, and build steps from frontend/. The build job only runs after backend tests and frontend checks pass.

## Create the new Git repository

From the clean deploy root:

    git init
    git add .
    git commit -m "Initial deploy"
    git branch -M main
    git remote add origin <new-repository-url>
    git push -u origin main
