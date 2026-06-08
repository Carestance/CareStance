# Frontend (Vercel Deployment)

This folder contains the frontend assets and configuration for Vercel deployment.

## Folder Structure

```
frontend/
├── templates/          # Jinja2 HTML templates (served by FastAPI backend)
├── static/             # CSS, JavaScript, images, and uploads
│   ├── css/           # Stylesheets (Tailwind-based)
│   ├── images/        # Images and assets
│   ├── js/            # JavaScript files
│   ├── manuals/       # User manuals and docs
│   └── uploads/       # User-generated uploads
├── index.html         # Static landing page (Vercel serves this)
├── style.css          # Placeholder styling
├── package.json       # NPM dependencies (Tailwind, etc.)
├── tailwind.config.js # Tailwind CSS configuration
├── input.css          # Tailwind input styles
├── vercel.json        # Vercel deployment configuration
└── README.md          # This file
```

## How It Works

### During Development
- **Backend** (Railway): Serves Jinja2 templates from `frontend/templates/` as HTML
- **Static assets**: Served from `frontend/static/` via FastAPI's StaticFiles mount at `/static`

### On Vercel (Production)
- Vercel deploys the `frontend/` folder as a static site
- `index.html` is the entry point
- All other HTML/CSS/JS assets are served as-is

### Hybrid Approach
- Keep Jinja2 templates in `frontend/templates/` for server-rendered pages on Railway
- Keep static assets in `frontend/static/` for both Railway and Vercel
- Use `frontend/index.html` as a Vercel landing page

## Development

### Edit Templates
1. Modify files in `frontend/templates/` (e.g., `landing.html`, `dashboard.html`)
2. These are served by the FastAPI backend when you run `python run.py`
3. Changes auto-reload in development mode

### Edit Styles
1. Edit `frontend/static/css/` directly or
2. Update `input.css` and run Tailwind:
   ```bash
   cd frontend
   npx tailwindcss -i input.css -o static/css/output.css --watch
   ```

### Edit Static Assets
1. Add images to `frontend/static/images/`
2. Reference them in HTML as `/static/images/filename.ext`

## Vercel Deployment

### Prerequisites
- Vercel account
- GitHub repository connected

### Steps
1. In Vercel dashboard, create a new project
2. Set **Project Root** to `frontend/`
3. Use the existing `vercel.json` configuration
4. Add **Environment Variables**:
   - `NEXT_PUBLIC_API_URL=https://your-railway-backend.up.railway.app`
5. Deploy!

### Accessing Vercel Frontend
- Vercel URL: `https://your-project.vercel.app`
- API calls should target your Railway backend

## Upgrading to React/Next.js/Vite

If you want to replace this static setup with a modern frontend framework:

1. Create a new project:
   ```bash
   cd frontend
   npm create vite@latest . -- --template react
   # or
   npx create-next-app@latest .
   ```

2. Update `vercel.json` to build the framework app:
   ```json
   {
     "buildCommand": "npm run build",
     "outputDirectory": "dist"
   }
   ```

3. Update your API calls to use the Railway backend URL

4. Deploy as usual

## Backend Integration

The **backend** (running on Railway) still serves:
- Jinja2 templates from `frontend/templates/` at routes like `/`, `/dashboard`, `/assessment`, etc.
- Static assets from `frontend/static/` at paths like `/static/css/...`, `/static/images/...`

The **frontend** (on Vercel) serves:
- Static HTML from `frontend/index.html`
- All assets in `frontend/static/`

## Troubleshooting

- **Styles not loading**: Check that `/static/` routes are accessible from your backend
- **Images not showing**: Verify paths are relative to `/static/` (e.g., `/static/images/logo.png`)
- **API calls failing**: Ensure `NEXT_PUBLIC_API_URL` environment variable is set on Vercel

## See Also

- [DEPLOYMENT.md](../DEPLOYMENT.md) – Full deployment guide
- [README.md](../README.md) – Main project README
- [Vercel Documentation](https://vercel.com/docs)
