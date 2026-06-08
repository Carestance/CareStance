# Deployment Guide

This repo is now organized for a split deployment:

- `frontend/` → deploy on Vercel
- repo root → backend deploy on Railway (current Python FastAPI app)

## Backend on Railway

### What to deploy

- `requirements.txt`
- `run.py`
- `app/`
- `api/`
- `Dockerfile` and `docker-compose.yml` (optional)
- `.env.example` for local development

### Steps

1. Sign in to Railway and create a new project.
2. Connect your GitHub repository.
3. Set the root directory to the repository root.
4. Add environment variables in Railway:
   - `DATABASE_URL`
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`
   - `ADMIN_EMAIL`
   - `SECRET_KEY`
   - `REDIS_URL`
   - `BASE_URL` or `APP_URL` set to your Railway URL if needed
5. Set the start command to:
   - `python run.py`
6. If Railway creates a Docker-based service, you can use the existing `Dockerfile`.

### Local testing

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

## Frontend on Vercel

### What to deploy

- `frontend/` folder only

### Steps

1. Sign in to Vercel and create a new project.
2. Connect the same repo.
3. Set the project root to `frontend/`.
4. Ensure Vercel uses `frontend/vercel.json`.
5. If your frontend app calls the backend API, add an environment variable such as `NEXT_PUBLIC_API_URL` or `VITE_API_URL` with your Railway backend URL.

### Example Vercel environment variable

- `NEXT_PUBLIC_API_URL=https://your-backend-production.up.railway.app`

## Notes

- The existing Python app is currently a server-rendered FastAPI/Jinja app, so the frontend folder is a separate deployment stub.
- If you want a full frontend app, replace the placeholder page in `frontend/` with your actual React/Next/Vite project.
- Remove `frontend/` from the root deploy target so Vercel does not deploy the backend accidentally.
