# Quick Deployment Reference

## TL;DR

### Railway Backend (FastAPI)
```bash
# 1. Push to GitHub
git push origin main

# 2. Railway auto-detects and deploys from repo root
# Set environment variables in Railway dashboard:
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret
# (and other vars from .env.example)

# 3. Railway provides: https://carestance-prod.up.railway.app
```

### Vercel Frontend (Static Assets)
```bash
# 1. Push to GitHub
git push origin main

# 2. Create new Vercel project
# Select: Frontend folder as root
# Deploy from: frontend/

# 3. Vercel provides: https://carestance-frontend.vercel.app
```

---

## Environment Variables Checklist

### Railway Backend (app/main.py will access these)
- [ ] `DATABASE_URL` - PostgreSQL connection string
- [ ] `SECRET_KEY` - Random string for session signing
- [ ] `GEMINI_API_KEY` - Google Gemini API key
- [ ] `GROQ_API_KEY` - Groq LLM API key (fallback)
- [ ] `RAZORPAY_KEY_ID` - Razorpay merchant ID
- [ ] `RAZORPAY_KEY_SECRET` - Razorpay secret key
- [ ] `ADMIN_EMAIL` - Admin notification email
- [ ] `REDIS_URL` - Redis cache connection (optional)
- [ ] `BASE_URL` - Your Railway domain (e.g., `https://carestance.up.railway.app`)

### Vercel Frontend (frontend/static/js and templates)
- [ ] `NEXT_PUBLIC_API_URL` - Railway backend URL (e.g., `https://carestance.up.railway.app`)

---

## Common URLs After Deployment

| Component | URL Example |
|-----------|------------|
| Backend API | `https://carestance-prod.up.railway.app` |
| Frontend | `https://carestance-frontend.vercel.app` |
| API Health Check | `https://carestance-prod.up.railway.app/docs` |
| Home Page | `https://carestance-prod.up.railway.app/` |
| Dashboard | `https://carestance-prod.up.railway.app/dashboard` |

---

## Troubleshooting

### Backend not responding
```bash
# Check Railway logs for errors
# Verify DATABASE_URL is correct
# Ensure all required env vars are set
# Try: curl https://your-railway-url/docs
```

### Frontend can't reach backend
```bash
# Verify NEXT_PUBLIC_API_URL in Vercel env vars
# Check browser console for CORS errors
# Ensure backend API allows cross-origin requests
```

### Static files (CSS, images) not loading
```bash
# Verify frontend/static/ folder exists on Railway
# Check nginx.conf or app/main.py for static mount paths
# Ensure /static routes are not blocked
```

---

## Local Development vs Production

### Local
```bash
cd CareStance
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env with local values
python run.py
# Access at http://localhost:8000
```

### Production
- Backend: Railway auto-runs `python run.py` on push
- Frontend: Vercel auto-deploys static files on push
- No manual deployment needed; just push to GitHub!

---

## Monitoring

### Railway Dashboard
- Metrics tab: CPU, memory, network usage
- Logs tab: Real-time application logs
- Deployments tab: Rollback or redeploy previous versions

### Vercel Dashboard
- Deployments: View build logs and status
- Analytics: Page performance and usage
- Settings: Manage domains and env vars

---

## Emergency Rollback

### Railway
1. Go to Deployments
2. Select previous working deployment
3. Click "Redeploy"

### Vercel
1. Go to Deployments
2. Find previous working deployment
3. Click "Promote to Production"

---

## Further Help

- See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed step-by-step instructions
- See [README.md](./README.md) for local development
- See [CONTRIBUTING.md](./CONTRIBUTING.md) for code guidelines
