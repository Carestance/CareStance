# Frontend (Vercel)

This folder is the frontend deployment target for Vercel.

## What to use here

- Replace `index.html` with your real frontend application.
- Keep `vercel.json` in this folder so Vercel deploys `frontend/` as a static site.

## Current placeholder

- `index.html` is a simple placeholder page.
- `style.css` contains basic styling.

## Vercel setup

1. Create a new Vercel project.
2. Set the project root to `frontend/`.
3. Use the existing `frontend/vercel.json` configuration.
4. If your frontend app needs a backend URL, add an environment variable like `REACT_APP_API_URL` or `NEXT_PUBLIC_API_URL`.
