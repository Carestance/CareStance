# Deployment Guide: Railway (Backend) + Vercel (Frontend)

This repository is now organized for a **split deployment model**:

- **Backend (FastAPI)**: Deploy on Railway  
- **Frontend (static HTML + Tailwind CSS)**: Deploy on Vercel

---

## Backend Deployment on Railway

Railway will run the FastAPI backend server and serve the HTML templates and static assets.

### Prerequisites

- Railway account (https://railway.app)
- GitHub repository connected

### Files Deployed to Railway

```
├── requirements.txt       # Python dependencies
├── run.py                 # Server entry point
├── app/                   # FastAPI application
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── services/
│   ├── routes/
│   ├── utils/
│   └── assessment_data/
├── api/                   # Vercel serverless functions (optional backup)
├── scripts/               # Database utilities
├── data/                  # Static data files
├── frontend/              # Templates and static assets served by FastAPI
│   ├── templates/         # Jinja2 HTML templates
│   └── static/            # CSS, JS, images, uploads
├── Dockerfile             # (Optional) Docker configuration
└── .env.example           # Example environment variables
```

### Step-by-Step Deployment to Railway

#### 1. Create a New Railway Project

1. Log in to [Railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub"**
4. Authorize Railway to access your GitHub account
5. Select the `CareStance` repository
6. Railway will auto-detect the `Dockerfile` or Python project

#### 2. Configure Environment Variables

In the Railway dashboard, go to **Variables** and add:

```
DATABASE_URL=postgresql://user:password@host:5432/carestance
GEMINI_API_KEY=your-google-gemini-key
GROQ_API_KEY=your-groq-api-key
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret
ADMIN_EMAIL=admin@example.com
SECRET_KEY=your-random-secret-key-here
REDIS_URL=redis://host:6379/0
BASE_URL=https://your-railway-app.up.railway.app
VERCEL=false
```

#### 3. Configure Build & Start Commands

In the Railway settings:

- **Build Command**: (None required; Railway will auto-detect `requirements.txt`)
- **Start Command**:
  ```
  python run.py
  ```

#### 4. Add a PostgreSQL Database (Optional)

If you don't have an external database:

1. In Railway dashboard, click **"+ Add"** → **Postgres**
2. Railway will auto-populate the `DATABASE_URL` environment variable

#### 5. Deploy

1. Push your code to GitHub
2. Railway will automatically trigger a deployment
3. Wait for the build to complete
4. Once deployed, Railway provides a public URL (e.g., `https://carestance-prod.up.railway.app`)

#### 6. Verify Deployment

Visit `https://your-railway-app.up.railway.app/` in your browser. You should see the landing page.

### Troubleshooting Railway

- **Port issues**: Railway sets `PORT` environment variable automatically. Ensure `run.py` respects `os.getenv("PORT", "8000")`.
- **Static files not loading**: Verify `FRONTEND_DIR` paths in `app/main.py` are correct.
- **Database connection errors**: Check `DATABASE_URL` format and network access.

---

## Frontend Deployment on Vercel

Vercel will serve the static HTML, CSS, and JS from the `frontend/` folder as a separate frontend service.

### Prerequisites

- Vercel account (https://vercel.com)
- GitHub repository connected

### Files Deployed to Vercel

```
frontend/
├── index.html             # Main landing page
├── style.css              # Placeholder CSS
├── vercel.json            # Vercel configuration
├── package.json           # Frontend build config
├── package-lock.json      # Dependency lock
├── tailwind.config.js     # Tailwind CSS config
├── input.css              # Tailwind input
├── templates/             # Jinja2 templates (can also deploy as static)
└── static/                # Images, logos, styles, etc.
```

### Step-by-Step Deployment to Vercel

#### 1. Create a New Vercel Project

1. Log in to [Vercel.com](https://vercel.com)
2. Click **"Add New"** → **"Project"**
3. Select **"Import Git Repository"**
4. Authorize Vercel to access your GitHub account
5. Select the `CareStance` repository

#### 2. Configure Project Root

1. In the **Project Settings**, set:
   - **Root Directory**: `frontend/`
   - **Framework Preset**: (Leave as `Other`)
   - **Build Command**: (Optional; leave blank for static deployment)
   - **Output Directory**: (Leave blank)

#### 3. Add Environment Variables

Click **"Environment Variables"** and add:

```
NEXT_PUBLIC_API_URL=https://your-railway-app.up.railway.app
VITE_API_URL=https://your-railway-app.up.railway.app
```

*(Replace the URL with your actual Railway backend URL)*

#### 4. Deploy

1. Click **"Deploy"**
2. Vercel will build and deploy the `frontend/` folder
3. Once complete, Vercel provides a public URL (e.g., `https://carestance-frontend.vercel.app`)

#### 5. Update Backend API URL

If you need frontend pages to call the Railway backend API:

1. In your frontend code (templates or static JS), ensure API calls use the `NEXT_PUBLIC_API_URL` environment variable:
   ```javascript
   const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
   fetch(`${apiUrl}/api/endpoint`);
   ```

2. Or hardcode the Railway URL in `frontend/static/js/*.js` files.

### Troubleshooting Vercel

- **Deploy fails**: Ensure `frontend/vercel.json` exists and is valid JSON.
- **CSS not loading**: Check that `frontend/static/css/` files are referenced correctly in templates.
- **API calls fail**: Verify the `NEXT_PUBLIC_API_URL` environment variable matches your Railway backend URL.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────┐
│                   USER BROWSER                   │
│  https://carestance-frontend.vercel.app          │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
    ┌─────▼──────┐    ┌─────▼────────────┐
    │   Static   │    │  API Calls       │
    │   HTML/CSS │    │  (JSON)          │
    │   (Vercel) │    │                  │
    └────────────┘    └─────┬────────────┘
                             │
                      ┌──────▼──────────┐
                      │   Railway       │
                      │   Backend       │
                      │   (FastAPI)     │
                      │ :8000           │
                      └──────┬──────────┘
                             │
                      ┌──────▼──────────┐
                      │   PostgreSQL    │
                      │   Database      │
                      └─────────────────┘
```

---

## Local Development

### Backend (Railway equivalent)

```powershell
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

# Edit .env with your local database URL and API keys
python run.py
# Server runs at http://localhost:8000
```

### Frontend (Vercel equivalent)

For a static frontend (current setup):
- Edit `frontend/index.html` directly or add more `.html` files
- Add CSS in `frontend/static/css/`
- No build step required

For a dynamic frontend (React/Vite/Next.js):
```bash
cd frontend
npm install
npm run dev
# Dev server runs at http://localhost:3000 (varies by framework)
```

---

## Monitoring & Logs

### Railway Logs
- Dashboard → Select your service → **"Logs"** tab
- View real-time application output and errors

### Vercel Logs
- Dashboard → Select your project → **"Deployments"** tab
- Click on a deployment → **"Logs"** to see build and runtime output

---

## Next Steps

1. **Deploy backend** to Railway following the steps above
2. **Deploy frontend** to Vercel, pointing to your Railway URL
3. **Test end-to-end**: Visit the Vercel frontend and ensure API calls reach the Railway backend
4. **Set up CI/CD**: Both Railway and Vercel auto-deploy on GitHub push
5. **Monitor logs** and set up alerts for production issues
