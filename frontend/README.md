# Frontend

This folder is a standalone Next.js application. It calls the PipeSmith FastAPI service only through the HTTP API URL configured with NEXT_PUBLIC_API_URL.

## Local development

1. Copy .env.example to .env.local.
2. Keep NEXT_PUBLIC_API_URL=http://localhost:8000 when the backend runs locally.
3. Install dependencies with npm ci, then start the development server with npm run dev.

## Vercel

Use this folder as the Vercel Root Directory and keep the default Next.js output handling. Set NEXT_PUBLIC_API_URL to the deployed backend URL in the Vercel environment settings, then redeploy.
