CareStance — Intern Onboarding Guide

Welcome! This repository contains CareStance, an AI-powered career assessment and guidance platform built with FastAPI and Jinja2 templates. This README is tailored for interns: quick setup, where to start, common tasks, and how to contribute.

---

## Deployment Architecture

This project uses a **split deployment model**:

- **Backend (FastAPI)** → Deploy on [Railway](https://railway.app)
  - Serves API endpoints and Jinja2 HTML templates
  - Handles database, authentication, and AI logic
  - URL: `https://your-app.up.railway.app`

- **Frontend (Static Assets)** → Deploy on [Vercel](https://vercel.com)
  - Serves HTML, CSS, JS from `frontend/` folder
  - Can be replaced with React/Next.js/Vite later
  - URL: `https://your-app.vercel.app`

📖 **See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment steps**
⚡ **See [QUICKSTART_DEPLOY.md](./QUICKSTART_DEPLOY.md) for quick reference**

---

## Quick Start (Windows)

1. Clone the repo and create a virtual environment:

```powershell
git clone https://github.com/Carestance/CareStance.git
cd CareStance
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a local environment file only when you need external integrations:

```powershell
New-Item -ItemType File -Path .env -Force
# Edit .env and add the keys you need (see Environment Variables below)
```

3. Run the application locally:

```powershell
python run.py
# App: http://127.0.0.1:8080
```

If using WSL/Unix, use `source .venv/bin/activate` instead of the PowerShell activate command.

---

## Environment Variables (required for local dev)

- GEMINI_API_KEY — Google Gemini API key (optional for some flows)
- GROQ_API_KEY — Groq (fallback LLM) API key (optional)
- RAZORPAY_KEY_ID — Razorpay test key id (payments)
- RAZORPAY_KEY_SECRET — Razorpay test key secret
- ADMIN_EMAIL — Default admin email for notifications
- SECRET_KEY — FastAPI secret for sessions/cookies
- REDIS_URL — Redis connection string (if using caching/session store)

Place these in `.env` at the project root. For interns, it's OK to run without AI keys — some features will be disabled or use mock behavior.

---

## Where to Start (for interns)

- App entrypoint: `app/main.py` — sets up the FastAPI app and routes.
- Core routes: `app/routes/` — look at `payments.py` and other route modules.
- Services: `app/services/` — integration code (e.g., `razorpay_service.py`).
- Database and models: `app/database.py` and `app/models.py` — SQLAlchemy setup and ORM models.
- Templates: `frontend/templates/` — Jinja2 HTML templates.
- Static assets: `frontend/static/` — CSS, JS, images, uploads.
- Utility scripts: `scripts/` — useful maintenance and migration helpers.

Recommended first tasks for interns:
- Fix small template bugs in `app/templates/` and preview changes by running locally.
- Add unit tests for a single route or utility in `tests/`.
- Improve documentation for a small module (e.g., `app/services/razorpay_service.py`).

---

## Common Commands

Activate venv (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
python run.py
```

The default local URL is `http://localhost:8080`. To enable automatic reload
while developing, set `DEV_RELOAD=true` in `.env` before starting the app.

Run a single script (example):

```powershell
python scripts/list_users.py
```

Run tests (if any):

```powershell
pytest -q
```

Validate backend and Jinja templates before raising a PR:

```powershell
.\.venv\Scripts\python.exe -m py_compile app\main.py app\models.py
.\.venv\Scripts\python.exe -c "from jinja2 import Environment, FileSystemLoader; e=Environment(loader=FileSystemLoader('frontend/templates')); e.get_template('counsellor_dashboard.html'); e.get_template('teacher_student_detail.html'); print('Templates OK')"
git diff --check
```

### Test the teacher/student dashboard

1. Start the application and open `http://localhost:8080/login`.
2. Log in as a student, open `/counsellors`, and book a session with a counsellor.
3. Complete the assessment and generate a growth map to populate progress data.
4. Log in as that counsellor and open `/dashboard` → **Students**.
5. Open a student name to verify the development summary, roadmap tasks, timeline, and private teacher notes.

Only students assigned through an appointment are visible to a counsellor. The
teacher view intentionally excludes contact details and raw assessment answers.

---

## Project Structure (short)

- `app/` — application code (routes, services, templates, models)
- `frontend/` — frontend assets (HTML templates, CSS, JS, static files)
- `scripts/` — maintenance and utility scripts (organized into backups, debug, maintenance, migrations, seeds, verification)
- `tests/` — unit and integration tests
- `data/` — static question sets and other data used by assessments
- `archive/` — legacy helpers and old migration files (do not change)
- `run.py` — simple runner for local development
- `requirements.txt` — Python dependencies

See the full tree in the repo for more files.

---

## Development Guidelines (for interns)

- Branches: create feature branches: `feature/<short-description>` or `fix/<short-description>`.
- Commit messages: short, present tense. Example: "Add unit tests for appointment model".
- Pull Requests: target `main` (or `develop` if present). Include a short description and testing steps.
- Tests: add tests for your changes where practical. Keep changes focused and small.
- Secrets: Never commit API keys or `.env` files.

Code style:
- Use clear function names and avoid single-letter variables.
- Keep functions small (single responsibility).

---

## Useful Scripts

- `python scripts/list_users.py` — list users in DB
- `python scripts/manage_test_data.py` — seed or clear test data
- `python scripts/verify_classification.py` — debug LLM classification outputs

---

## Troubleshooting

- If the server fails to start, inspect `server.log` for stack traces.
- If missing packages: run `pip install -r requirements.txt`.
- If you see migration or DB issues, check `carestance.db` and `db_schema.txt`.

---

## How to Contribute

Please read `CONTRIBUTING.md` for the contribution workflow, PR checklist, and coding standards. Small, well-documented PRs are preferred for interns.

---

## Where to Ask Questions

- Add comments to your PR describing what you changed and why.
- Tag the mentor or repository owner in the PR (or create an issue if unsure).

---

## License

MIT License — CareStance Team

---

If you'd like, I can also add an `ONBOARDING.md` checklist and an issue/PR template. Tell me if you'd like those created now.
