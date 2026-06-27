import json
import uuid
import random
import datetime
import asyncio
import os
import shutil
import warnings
from functools import lru_cache
from types import SimpleNamespace
from . import email_utils
from .appwrite_client import databases, tables_db, account, storage, DB_ID, COLLECTIONS
from .appwrite_helper import get_user_by_id, get_user_by_email, update_assessment_simulation, sync_assessment_to_appwrite
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, Response, BackgroundTasks, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, and_, or_, func
from .database import AsyncSessionLocal, engine, get_db, Base, SQLALCHEMY_DATABASE_URL
import re

def sync_assessment_to_appwrite(user_id, result):
    pass  # Appwrite sync disabled — local DB only

from urllib.parse import urlparse
from . import models
from .email_utils import (
    send_email, 
    get_booking_template, 
    get_cancellation_template, 
    get_reset_password_template, 
    get_connection_request_template
)
from itsdangerous import URLSafeTimedSerializer
from .data.career_keywords import career_keywords
from .utils.resource_aggregator import ResourceAggregator
from .services import simulation_service
from .services import assessment_engine

try:
    from app.pipeline.feature_extractor import FeatureExtractor
    extractor_tool = FeatureExtractor()
except Exception as e:
    print(f"FeatureExtractor Load Error: {e}")
    extractor_tool = None
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RUN_MIGRATIONS_ON_STARTUP = os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").strip().lower() in ("1", "true", "yes")
ENABLE_CLEANUP_TASK = os.getenv("ENABLE_CLEANUP_TASK", "false").strip().lower() in ("1", "true", "yes")

@lru_cache(maxsize=4)
def get_genai_module():
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    return genai

@lru_cache(maxsize=4)
def get_gemini_model(model_name: str):
    genai = get_genai_module()
    return genai.GenerativeModel(model_name)

@lru_cache(maxsize=1)
def get_groq_client():
    if not GROQ_API_KEY:
        return None
    from groq import AsyncGroq
    return AsyncGroq(api_key=GROQ_API_KEY)

# OAuth Setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Password Reset Serializer
serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY", "a_very_secret_key_for_sessions"))

# Razorpay Client
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_your_key_id")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "your_key_secret")
razorpay_client = None

def get_razorpay_client():
    global razorpay_client
    if razorpay_client is None:
        import razorpay
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return razorpay_client

from .utils.redis_cache import ai_cache
from .utils.cache_utils import user_cache

async def generate_content_with_fallback(prompt):
    """
    Attempts to generate content using Groq primarily, with fallback to Gemini.
    Uses Redis caching to avoid repetitive API calls.
    """
    # Check Cache
    cached_response = ai_cache.get(prompt)
    if cached_response:
        print("AI CACHE HIT")
        return cached_response

    print("AI CACHE MISS")
    
    # Try Groq first as requested
    gclient = get_groq_client()
    text = None
    groq_err = None
    if gclient:
        try:
            chat_completion = await gclient.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            )
            text = chat_completion.choices[0].message.content
        except Exception as e:
            groq_err = e
            print(f"Groq Error (Switching to Gemini): {e}")
    else:
        print("Groq client not available. Falling back to Gemini.")

    if not text:
        # Fallback to Gemini
        try:
            model = get_gemini_model("gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            text = response.text
        except Exception as gemini_e:
            raise Exception(f"Dual API Failure. Groq: {groq_err}, Gemini: {gemini_e}")

    # --- Robust Multi-Layer JSON Repair ---
    # Layer 1: Try json_repair (handles most LLM malformed JSON automatically)
    try:
        from json_repair import repair_json
        # Strip markdown fences first
        cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
        # Extract the outermost JSON object
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')
        if start_idx != -1 and end_idx != -1:
            cleaned = cleaned[start_idx:end_idx + 1]
        repaired = repair_json(cleaned, return_objects=False)
        # Validate it round-trips as valid JSON
        json.loads(repaired)
        ai_cache.set(prompt, repaired)
        return repaired
    except Exception as repair_err:
        print(f"json_repair failed, falling back to regex cleanup: {repair_err}")

    # Layer 2: Regex-based cleanup (trailing commas, whitespace issues)
    try:
        cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')
        if start_idx != -1 and end_idx != -1:
            cleaned = cleaned[start_idx:end_idx + 1]
        # Remove trailing commas before } or ]
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        # Validate
        json.loads(cleaned)
        ai_cache.set(prompt, cleaned)
        return cleaned
    except Exception:
        pass

    # Layer 3: Return raw text as last resort (let caller handle it)
    ai_cache.set(prompt, text)
    return text

async def check_content_moderation(text_content: str):
    """
    Checks if the given text contains abusive or inappropriate content using the AI model.
    Returns: (is_flagged, reason)
    """
    moderation_prompt = f"""
    Analyze the following text for abusive language, hate speech, harassment, or highly inappropriate content for a student career guidance platform.
    Text: "{text_content}"
    
    Respond STRICTLY in JSON format:
    {{
      "is_flagged": boolean,
      "reason": "string describing the violation or 'None'"
    }}
    """
    try:
        response_json_str = await generate_content_with_fallback(moderation_prompt)
        data = json.loads(response_json_str)
        return data.get("is_flagged", False), data.get("reason", "None")
    except Exception as e:
        print(f"Moderation Error: {e}")
        return False, "None"

from .data.questions_data import questions
from .data.questions_12th import questions_12th
from .data.questions_above_12th import questions_above_12th

# Auto-migrate: add missing columns to existing tables
async def run_migrations():
    """Add new columns to existing tables if they don't exist."""
    from sqlalchemy import text, inspect
    
    try:
        async with engine.begin() as conn:
            inspector = await conn.run_sync(inspect)

            # Get existing columns for each table
            def get_columns(table_name):
                try:
                    return [col['name'] for col in inspector.get_columns(table_name)]
                except Exception:
                    return []

            migrations = []

            # 1. Users table
            u_cols = get_columns('users')
            print(f"DEBUG MIGRATION: Found columns for 'users': {u_cols}", flush=True)
            
            # Always attempt to check/add these columns
            if 'profile_photo' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN profile_photo VARCHAR")
            if 'bio' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN bio TEXT")
            if 'is_suspended' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN is_suspended BOOLEAN DEFAULT FALSE")
            if 'contact_number' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN contact_number VARCHAR")
            if 'full_name' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN full_name VARCHAR")
            if 'role' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN role VARCHAR")
            if 'onboarded' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN onboarded BOOLEAN DEFAULT FALSE")
            if 'simulations_completed' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN simulations_completed INTEGER DEFAULT 0")
            if 'simulation_paid' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN simulation_paid BOOLEAN DEFAULT FALSE")
            if 'simulation_credits' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN simulation_credits INTEGER DEFAULT 0")
            if 'created_at' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
            if 'last_login' not in u_cols: migrations.append("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_full_name ON users (full_name)")
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_onboarded ON users (onboarded)")

            # 2. Counsellor Profiles
            cp_cols = get_columns('counsellor_profiles')
            if cp_cols:
                checklist = [
                    ('tnc_accepted', "BOOLEAN DEFAULT FALSE"), ('tnc_accepted_at', "TIMESTAMP"),
                    ('is_blocked', "BOOLEAN DEFAULT FALSE"), ('block_reason', "VARCHAR"),
                    ('certificates', "TEXT"), ('experience', "TEXT"),
                    ('is_verified', "BOOLEAN DEFAULT FALSE"), ('verification_status', "VARCHAR DEFAULT 'pending'"),
                    ('fee_locked', "BOOLEAN DEFAULT FALSE"), ('razorpay_account_id', "VARCHAR"),
                    ('onboarding_status', "VARCHAR DEFAULT 'not_started'"), ('razorpay_contact_id', "VARCHAR"),
                    ('razorpay_fund_account_id', "VARCHAR"), ('average_rating', "FLOAT DEFAULT 5.0"),
                    ('rating_count', "INTEGER DEFAULT 0"), ('is_founding_counsellor', "BOOLEAN DEFAULT FALSE"),
                    ('founding_badge_awarded_at', "TIMESTAMP"), ('commission_free_until', "TIMESTAMP")
                ]
                for col, ty in checklist:
                    if col not in cp_cols: migrations.append(f"ALTER TABLE counsellor_profiles ADD COLUMN {col} {ty}")

            # 3. Appointments
            ap_cols = get_columns('appointments')
            if ap_cols:
                for col, ty in [('counsellor_joined', 'BOOLEAN DEFAULT FALSE'), ('joined_at', 'TIMESTAMP'), 
                               ('student_joined', 'BOOLEAN DEFAULT FALSE'), ('student_joined_at', 'TIMESTAMP'),
                               ('actual_overlap_minutes', 'INTEGER DEFAULT 0'),
                               ('cancelled_by', 'VARCHAR'), ('cancelled_by_role', 'VARCHAR')]:
                    if col not in ap_cols: migrations.append(f"ALTER TABLE appointments ADD COLUMN {col} {ty}")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_appointments_appointment_time ON appointments (appointment_time)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_appointments_payment_status ON appointments (payment_status)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_appointments_cancelled_by ON appointments (cancelled_by)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_appointments_cancelled_by_role ON appointments (cancelled_by_role)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_chat_messages_timestamp ON chat_messages (timestamp)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_chat_messages_sender ON chat_messages (sender)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_feedbacks_user_id ON feedbacks (user_id)")

            # 4. Student Messages
            sm_cols = get_columns('student_messages')
            if sm_cols:
                if 'attachment_path' not in sm_cols: migrations.append("ALTER TABLE student_messages ADD COLUMN attachment_path VARCHAR")
                if 'attachment_type' not in sm_cols: migrations.append("ALTER TABLE student_messages ADD COLUMN attachment_type VARCHAR")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_student_messages_timestamp ON student_messages (timestamp)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_student_messages_is_read ON student_messages (is_read)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_career_paths_career_title ON career_paths (career_title)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_college_recommendations_career_title ON college_recommendations (career_title)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_counsellor_ratings_rating ON counsellor_ratings (rating)")

            # 5. Assessment Results
            ar_cols = get_columns('assessment_results')
            if ar_cols:
                for col, ty in [('selected_class', 'VARCHAR'), ('phase3_result', 'VARCHAR'), 
                               ('phase3_answers', 'JSON'), ('phase3_analysis', 'TEXT'),
                               ('final_answers', 'JSON'), ('stream_scores', 'JSON'),
                               ('recommended_stream', 'VARCHAR'), ('final_analysis', 'TEXT'),
                               ('stream_pros', 'JSON'), ('stream_cons', 'JSON'),
                               ('simulation_career', 'VARCHAR'), ('simulation_questions', 'JSON'),
                               ('simulation_answers', 'JSON'), ('simulation_evaluation', 'JSON'),
                               ('simulations_completed', 'INTEGER DEFAULT 0'), ('simulation_paid', 'BOOLEAN DEFAULT FALSE'),
                               ('simulation_credits', 'INTEGER DEFAULT 0'),
                               ('student_type', "VARCHAR DEFAULT '10th'"), ('current_phase', 'INTEGER DEFAULT 1'),
                               ('intake_turn', 'INTEGER DEFAULT 1'), ('intake_name', 'VARCHAR'),
                               ('intake_grade', 'INTEGER'), ('intake_stream', 'VARCHAR'),
                               ('telemetry_logs', 'JSON'),
                               ('chat_messages', 'JSON'), ('chat_turn', 'INTEGER DEFAULT 0'),
                               ('proxy_answers', 'JSON'), ('scenario_answers', 'JSON'),
                               ('assessment_report', 'JSON')]:
                    if col not in ar_cols: migrations.append(f"ALTER TABLE assessment_results ADD COLUMN {col} {ty}")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_assessment_results_recommended_stream ON assessment_results (recommended_stream)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_assessment_results_phase_2_category ON assessment_results (phase_2_category)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_assessment_results_personality ON assessment_results (personality)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_assessment_results_selected_class ON assessment_results (selected_class)")
                
            # 6. Notifications
            n_cols = get_columns('notifications')
            if n_cols:
                migrations.append("CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)")
                migrations.append("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read)")

            # 7. Simulation Payments
            sp_cols = get_columns('simulation_payments')
            if sp_cols is None:
                migrations.append("""
                CREATE TABLE simulation_payments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    razorpay_order_id VARCHAR,
                    razorpay_payment_id VARCHAR,
                    amount FLOAT,
                    career VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

            # 8. Moderation Flags
            mf_cols = get_columns('moderation_flags')
            if mf_cols:
                for col, ty in [('flag_type', 'VARCHAR'), ('severity', 'VARCHAR'), ('admin_note', 'TEXT')]:
                    if col not in mf_cols: migrations.append(f"ALTER TABLE moderation_flags ADD COLUMN {col} {ty}")

            # 9. Tickets
            t_cols = get_columns('tickets')
            if t_cols:
                if 'updated_at' not in t_cols: migrations.append("ALTER TABLE tickets ADD COLUMN updated_at TIMESTAMP")

            # 10. Simulation Payments
            sp_cols2 = get_columns('simulation_payments')
            if sp_cols2:
                if 'status' not in sp_cols2: migrations.append("ALTER TABLE simulation_payments ADD COLUMN status VARCHAR DEFAULT 'success'")

            # 11. Counsellor Profiles
            if cp_cols:
                if 'verification_remarks' not in cp_cols: migrations.append("ALTER TABLE counsellor_profiles ADD COLUMN verification_remarks TEXT")

        if migrations:
            print(f"DEBUG: Found {len(migrations)} pending migrations.", flush=True)
            async with engine.begin() as conn:
                for sql in migrations:
                    try:
                        from sqlalchemy import text
                        await conn.execute(text(sql))
                        print(f"DATABASE MIGRATION SUCCESS: {sql}", flush=True)
                    except Exception as me:
                        print(f"DATABASE MIGRATION SKIP/ERROR: {sql} -> {me}", flush=True)
            print(f"DATABASE: Finished running {len(migrations)} migration queries.", flush=True)
        else:
            print("DATABASE: No new migrations detected.", flush=True)
    except Exception as e:
        print(f"DATABASE FATAL ERROR during migration check: {e}", flush=True)
        import traceback
        traceback.print_exc()


app = FastAPI(title="CareStance")

@app.middleware("http")
async def forward_proto_middleware(request: Request, call_next):
    proto = request.headers.get("x-forwarded-proto")
    if proto:
        request.scope["scheme"] = proto
    return await call_next(request)

# Lightweight health endpoint for uptime checks
@app.get("/_health")
async def _health():
    return {"status": "ok", "now": datetime.datetime.utcnow().isoformat()}

@app.on_event("startup")
async def startup_event():
    """Run migrations on startup for local development and when explicitly enabled."""
    try:
        # EMERGENCY FIX: Force add missing columns to 'users' table in ONE batch
        async with engine.begin() as conn:
            from sqlalchemy import text
            try:
                # Grouping into one command is much faster and prevents startup timeouts
                # Note: IF NOT EXISTS is used for each column for safety
                sql = """
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS profile_photo VARCHAR,
                ADD COLUMN IF NOT EXISTS bio TEXT,
                ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS contact_number VARCHAR,
                ADD COLUMN IF NOT EXISTS full_name VARCHAR,
                ADD COLUMN IF NOT EXISTS role VARCHAR,
                ADD COLUMN IF NOT EXISTS onboarded BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS simulations_completed INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS simulation_paid BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS simulation_credits INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
                ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
                """
                await conn.execute(text(sql))
                print("DEBUG: Emergency batch migration for 'users' table completed.", flush=True)
                # 2. Counsellor Profiles table
                sql_cp = """
                ALTER TABLE counsellor_profiles 
                ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS block_reason VARCHAR,
                ADD COLUMN IF NOT EXISTS verification_remarks TEXT,
                ADD COLUMN IF NOT EXISTS fee_locked BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS razorpay_account_id VARCHAR,
                ADD COLUMN IF NOT EXISTS onboarding_status VARCHAR DEFAULT 'not_started',
                ADD COLUMN IF NOT EXISTS razorpay_contact_id VARCHAR,
                ADD COLUMN IF NOT EXISTS razorpay_fund_account_id VARCHAR,
                ADD COLUMN IF NOT EXISTS is_founding_counsellor BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS founding_badge_awarded_at TIMESTAMP,
                ADD COLUMN IF NOT EXISTS commission_free_until TIMESTAMP,
                ADD COLUMN IF NOT EXISTS tnc_accepted BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS tnc_accepted_at TIMESTAMP;
                """
                await conn.execute(text(sql_cp))
                print("DEBUG: Emergency batch migration for 'counsellor_profiles' table completed.", flush=True)
            except Exception as e:
                print(f"DEBUG: Emergency batch migration failed (likely already patched): {e}", flush=True)

        if RUN_MIGRATIONS_ON_STARTUP or SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
            # Create all tables asynchronously and run any schema migrations
            async with engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
            await run_migrations()
        else:
            print("Startup: Skipping DB migration and schema creation. Set RUN_MIGRATIONS_ON_STARTUP=true to enable.")
    except Exception as e:
        print(f"Startup database error: {e}")

    if ENABLE_CLEANUP_TASK:
        app.state.cleanup_stop = asyncio.Event()
        app.state.cleanup_task = asyncio.create_task(_cleanup_old_sessions_loop(app.state.cleanup_stop))
    else:
        print("Startup: Auto-cleanup task disabled. Set ENABLE_CLEANUP_TASK=true to enable.")

async def _cleanup_old_sessions_loop(stop_event: asyncio.Event):
    """Periodically delete completed/expired video session appointments older than 2 days."""
    while not stop_event.is_set():
        try:
            async with AsyncSessionLocal() as db:
                cutoff = datetime.datetime.now() - datetime.timedelta(days=2)
                # Delete old ratings first (FK dependency)
                stmt_ratings = select(models.CounselorRating).where(
                    models.CounselorRating.appointment_id.in_(
                        select(models.Appointment.id).where(
                            and_(
                                models.Appointment.status.in_(["completed", "scheduled"]),
                                models.Appointment.appointment_time < cutoff
                            )
                        )
                    )
                )
                ratings_result = await db.execute(stmt_ratings)
                deleted_count = 0
                for rating in ratings_result.scalars().all():
                    await db.delete(rating)
                    deleted_count += 1
                
                # Delete old appointments
                stmt_appointments = select(models.Appointment).where(
                    and_(
                        models.Appointment.status.in_(["completed", "scheduled"]),
                        models.Appointment.appointment_time < cutoff
                    )
                )
                appt_result = await db.execute(stmt_appointments)
                for appt in appt_result.scalars().all():
                    await db.delete(appt)
                    deleted_count += 1
                
                if deleted_count > 0:
                    await db.commit()
                    print(f"AUTO-CLEANUP: Deleted {deleted_count} old video session(s) older than 2 days.")
                else:
                    await db.commit()
        except Exception as e:
            print(f"AUTO-CLEANUP ERROR: {e}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=6 * 60 * 60)
        except asyncio.TimeoutError:
            continue

@app.on_event("shutdown")
async def shutdown_event():
    stop_event = getattr(app.state, 'cleanup_stop', None)
    cleanup_task = getattr(app.state, 'cleanup_task', None)
    if stop_event:
        stop_event.set()
    if cleanup_task:
        await cleanup_task

# ─── Include Split Payments Router (Razorpay Route) ───────────────────────────
from .routes.payments import router as payments_router
app.include_router(payments_router)

from .routes import admin
app.include_router(admin.router)

# Global Exception Handler for better debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"GLOBAL ERROR: {exc}", flush=True)
    traceback.print_exc()
    try:
        return templates.TemplateResponse(
            request=request,
            name="error_update.html",
            context={"error": str(exc)},
            status_code=500
        )
    except Exception as template_exc:
        print(f"Error rendering error template: {template_exc}")
        return HTMLResponse(
            content=f"<html><body><h1>Internal Server Error</h1><p>We'll be right back. Fixed soon!</p></body></html>",
            status_code=500
        )

from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Helpers to include BASE_URL / APP_URL hosts and origins in middleware configuration
def _normalize_host(url: str):
    try:
        parsed = urlparse(url)
        return parsed.hostname or url
    except Exception:
        return url


def _normalize_origin(url: str):
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return url
    except Exception:
        return url


def _collect_env_hosts(*env_names):
    hosts = []
    for env in env_names:
        raw = os.getenv(env, "").strip()
        if raw:
            host = _normalize_host(raw)
            if host and host not in hosts:
                hosts.append(host)
    return hosts


def _collect_env_origins(*env_names):
    origins = []
    for env in env_names:
        raw = os.getenv(env, "").strip()
        if raw:
            origin = _normalize_origin(raw)
            if origin and origin not in origins:
                origins.append(origin)
    return origins

# ─── Trusted Host Middleware ──────────────────────────────────────────────────
# Ensures the app accepts requests from your domains
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=[
        "carestance.in", 
        "www.carestance.in", 
        "*.railway.app", 
        "localhost", 
        "127.0.0.1",
        *(_collect_env_hosts("BASE_URL", "APP_URL"))
    ]
)

# ─── CORS Middleware ──────────────────────────────────────────────────────────
# Allows Vercel and other configured domains to communicate with Railway
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://carestance.in", 
        "https://www.carestance.in", 
        "*.vercel.app",
        *(_collect_env_origins("BASE_URL", "APP_URL"))
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Session Middleware (needed for OAuth)
# On Vercel/production HTTPS, cookies should be secure.
_is_production = bool(os.getenv("VERCEL") or os.getenv("BASE_URL", os.getenv("APP_URL", "")).startswith("https"))

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "a_very_secret_key_for_sessions"),
    same_site="lax",
    https_only=_is_production,
    max_age=14 * 24 * 60 * 60,  # 14 days
)

# ─── Static Asset Caching Middleware ─────────────────────────────────────────
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        # Reduced cache to 1 hour to ensure updates propagate more reliably
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        # Prevent caching of dynamic HTML/API content to ensure users always see latest push
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def check_suspension(request: Request, call_next):
    # Paths that suspended users can still access
    exempt_paths = [
        "/suspended", 
        "/logout", 
        "/static", 
        "/login", 
        "/signup", 
        "/", 
        "/auth/google", 
        "/auth/callback",
        "/favicon.ico",
        "/ticket/submit"
    ]
    
    path = request.url.path
    # Check if the path is specifically exempt
    is_exempt = any(path == p or path.startswith("/static/") or path.startswith("/auth/") for p in exempt_paths)
    
    if not is_exempt:
        user_id = request.cookies.get("user_id")
        if user_id and user_id.strip(): # Added safety check for empty/invalid strings
            try:
                uid = int(user_id)
                # Quick check for suspension
                cached_status = user_cache.get_user_status(uid)
                if cached_status is None:
                    # Hit DB if cache is missing (e.g. first request or after invalidation)
                    from .database import AsyncSessionLocal
                    async with AsyncSessionLocal() as db_session:
                        from sqlalchemy import select
                        stmt = select(models.User).where(models.User.id == uid)
                        result = await db_session.execute(stmt)
                        user = result.scalars().first()
                        if user:
                            cached_status = {"is_suspended": user.is_suspended}
                            user_cache.set_user_status(uid, cached_status)
                
                if cached_status and cached_status.get("is_suspended"):
                    return RedirectResponse(url="/suspended", status_code=status.HTTP_302_FOUND)
            except Exception: pass

    # Skip caching for static files to keep response fast but headers default
    response = await call_next(request)
    return response

# Mount static assets and templates from the frontend folder
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Re-enabled cache as standard practice
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto"]) # Removed

def _get_bcrypt():
    import bcrypt
    return bcrypt


def verify_password(plain_password, hashed_password):
    bcrypt = _get_bcrypt()
    # Ensure bytes for bcrypt
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)

def get_password_hash(password):
    bcrypt = _get_bcrypt()
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id: return None
    try:
        # Try fetching from Appwrite first
        user = get_user_by_id(user_id)
        if user:
             return user
        
        # Fallback to local SQL if not found in Appwrite
        uid = int(user_id)
        stmt = select(models.User).options(selectinload(models.User.assessment)).where(models.User.id == uid)
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception: return None

# Routes

@app.get("/ads.txt")
async def ads_txt():
    # Looks for ads.txt in the project root (one level above 'app' folder)
    ads_path = os.path.join(ROOT_DIR, "ads.txt")
    if os.path.exists(ads_path):
        from fastapi.responses import FileResponse
        return FileResponse(ads_path)
    return Response(content="File not found", status_code=404)

@app.get("/BingSiteAuth.xml")
async def bing_site_auth():
    # Bing verification file in the project root
    bing_path = os.path.join(ROOT_DIR, "BingSiteAuth.xml")
    if os.path.exists(bing_path):
        from fastapi.responses import FileResponse
        return FileResponse(bing_path)
    return Response(content="File not found", status_code=404)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    try:
        # Bypassing Starlette's TemplateResponse to avoid internal dict vs string ambiguity
        template = templates.get_template("landing.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/founders", response_class=HTMLResponse)
async def founders_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    try:
        template = templates.get_template("founders.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/complete-onboarding")
async def complete_onboarding(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if user:
        user.onboarded = True
        await db.commit()
    return {"status": "success"}

@app.get("/articles", response_class=HTMLResponse)
async def articles_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    try:
        template = templates.get_template("articles.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/robots.txt")
async def robots_txt(request: Request):
    host = request.url.hostname or "carestance.in"
    content = f"User-agent: *\nAllow: /\nSitemap: https://{host}/sitemap.xml"
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml")
async def sitemap_xml(request: Request):
    # Simple static sitemap for now
    host = request.url.hostname or "carestance.in"
    scheme = request.url.scheme or "https"
    base_url = f"{scheme}://{host}"
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base_url}/</loc><priority>1.0</priority></url>
  <url><loc>{base_url}/signup</loc><priority>0.8</priority></url>
  <url><loc>{base_url}/login</loc><priority>0.8</priority></url>
  <url><loc>{base_url}/founders</loc><priority>0.7</priority></url>
  <url><loc>{base_url}/articles</loc><priority>0.9</priority></url>
  <url><loc>{base_url}/privacy</loc><priority>0.5</priority></url>
  <url><loc>{base_url}/terms</loc><priority>0.5</priority></url>
</urlset>"""
    return Response(content=content, media_type="application/xml")

@app.get("/admin/create-adsense-test-user")
async def create_adsense_test_user(db: AsyncSession = Depends(get_db)):
    # Create a user for AdSense crawler to use
    email = "adsense-tester@carestance.me"
    existing = (await db.execute(select(models.User).where(models.User.email == email))).scalars().first()
    if existing:
        return {"message": "User already exists", "email": email, "password": "CareStance2026!"}
    
    hashed_pw = get_password_hash("CareStance2026!")
    new_user = models.User(
        email=email, 
        hashed_password=hashed_pw, 
        full_name="AdSense Analytics Tester", 
        role="student",
        onboarded=True # Skip the onboarding for the bot
    )
    db.add(new_user)
    await db.commit()
    return {"message": "AdSense Test User Created Successfully", "email": email, "password": "CareStance2026!"}

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    try:
        template = templates.get_template("signup.html")
        content = template.render({"request": request})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    contact_number: str = Form(...),
    role: str = Form("student"),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check existing user local
    stmt = select(models.User).where(models.User.email == email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user:
        return templates.TemplateResponse(request=request, name="signup.html", context={"error": "Email already exists"})
    
    try:
        # 2. Create User in Appwrite Auth
        user_id = str(uuid.uuid4())[:20] # Appwrite ID limit
        try:
            appwrite_user = account.create(
                user_id=user_id,
                email=email,
                password=password,
                name=full_name
            )
        except Exception as ae:
            print(f"Appwrite Signup Error: {ae}")
            return templates.TemplateResponse(request=request, name="signup.html", context={"error": f"Appwrite error: {ae}"})

        # 3. Create User in Local DB
        hashed_pw = get_password_hash(password)
        new_user = models.User(id=None, email=email, hashed_password=hashed_pw, full_name=full_name, contact_number=contact_number, role=role)
        db.add(new_user)
        await db.flush()
        
        # 4. Create User Metadata in Appwrite DB
        try:
            tables_db.create_row(
                database_id=DB_ID,
                table_id=COLLECTIONS["users"],
                row_id=user_id,
                data={
                    "email": email,
                    "full_name": full_name,
                    "contact_number": contact_number,
                    "role": role,
                    "local_id": new_user.id
                }
            )
        except Exception as de:
            print(f"Appwrite DB Error: {de}")
            # Non-critical for now as we have local DB, but should be logged

        # Create Counsellor Profile
        if role == "counsellor":
            c_profile = models.CounsellorProfile(user_id=new_user.id)
            db.add(c_profile)
        
        await db.commit()
    except Exception as e:
        print(f"Signup error: {e}")
        await db.rollback()
        return templates.TemplateResponse(request=request, name="signup.html", context={"error": "An error occurred during signup. Please try again."})
    
    return RedirectResponse(url="/login?message=Account created with Appwrite! Please login.", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    try:
        template = templates.get_template("login.html")
        content = template.render({"request": request})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Try Appwrite Login first
    appwrite_user = None
    try:
        session = account.create_email_password_session(email, password)
        appwrite_user = get_user_by_email(email)
        print(f"Appwrite Login Success: {email}")
    except Exception as ae:
        print(f"Appwrite Login Failed: {ae}")
    
    # 2. Local verify (for transition/legacy fallback)
    stmt = select(models.User).where(models.User.email == email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    # If not in Appwrite and not local, error
    if not appwrite_user and (not user or not verify_password(password, user.hashed_password)):
         return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid credentials"})
    
    # Use local user if present; Appwrite user only if no local record exists.
    effective_user = user if user else appwrite_user
    effective_user_id = None
    if user:
        effective_user_id = user.id
    elif appwrite_user:
        effective_user_id = getattr(appwrite_user, "local_id", None)
        if effective_user_id is not None:
            try:
                effective_user_id = int(effective_user_id)
            except ValueError:
                pass

    try:
        # 2. Create Appwrite Session (Server-side)
        # Note: In a production app, you might want to handle sessions differently
        # but for now, we ensure the user exists and can authenticate in Appwrite.
        try:
            # We don't necessarily need to store the session on the server for every request
            # if we use local sessions, but we should verify the user can log in to Appwrite.
            session = account.create_email_password_session(email, password)
            print(f"Appwrite Session Created: {session['$id']}")
        except Exception as ae:
            print(f"Appwrite Login Error: {ae}")
            # If user exists locally but not in Appwrite (e.g. legacy user), we might need to sync them
            # For now, we'll just log it.
    except Exception as e:
        print(f"Login/Appwrite error: {e}")

    if effective_user_id is None and effective_user is not None:
        effective_user_id = getattr(effective_user, "id", None)

    # Pre-populate suspension cache
    user_cache.set_user_status(effective_user_id, {"is_suspended": getattr(effective_user, 'is_suspended', False)})
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    # 30 day persistent session
    response.set_cookie(
        key="user_id", 
        value=str(effective_user_id), 
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax"
    )
    return response

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user_id")
    return response

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    try:
        template = templates.get_template("forgot_password.html")
        content = template.render({"request": request})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/forgot-password")
async def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = (await db.execute(select(models.User).where(models.User.email == email))).scalars().first()
    if user:
        token = serializer.dumps(email, salt="password-reset-salt")
        reset_link = f"{request.base_url}reset-password/{token}"
        
        # Send Email
        background_tasks.add_task(
            send_email,
            email,
            "Reset Your CareStance Password 🔒",
            get_reset_password_template(user.full_name, reset_link)
        )
    
    # Always show success message for security (don't reveal if email exists)
    try:
        template = templates.get_template("forgot_password.html")
        content = template.render({
            "request": request, 
            "message": "If an account exists with that email, a reset link has been sent."
        })
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    try:
        # Token valid for 1 hour (3600 seconds)
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
        try:
            template = templates.get_template("forgot_password.html")
            content = template.render({
                "request": request, 
                "error": "The reset link is invalid or has expired."
            })
            return HTMLResponse(content=content)
        except Exception as e:
            import traceback
            return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)
    
    try:
        template = templates.get_template("reset_password.html")
        content = template.render({"request": request, "token": token})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/reset-password/{token}")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
         return templates.TemplateResponse(request=request, name="forgot_password.html", context={
            "error": "The reset link is invalid or has expired."
        })
    
    if password != confirm_password:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "token": token, 
            "error": "Passwords do not match"
        })
    
    user = (await db.execute(select(models.User).where(models.User.email == email))).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        user.hashed_password = get_password_hash(password)
        await db.commit()
    except Exception as e:
        print(f"Password reset error: {e}")
        await db.rollback()
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "token": token, 
            "error": "Failed to update password. Please try again."
        })
    
    return RedirectResponse(url="/login?message=Password updated successfully", status_code=status.HTTP_302_FOUND)

def get_oauth_redirect_uri(request: Request):
    host = request.headers.get("host", "")
    if "localhost" in host or "127.0.0.1" in host:
        return str(request.url_for('auth_callback'))
    
    base_url = os.getenv("BASE_URL") or os.getenv("APP_URL")
    if base_url:
        return f"{base_url.rstrip('/')}/auth/callback"
    else:
        redirect_uri = str(request.url_for('auth_callback'))
        if "vercel.app" in str(request.base_url) or os.getenv("VERCEL"):
            redirect_uri = redirect_uri.replace("http://", "https://")
        return redirect_uri

@app.get("/login/google")
async def login_google(request: Request):
    if not os.getenv('GOOGLE_CLIENT_ID'):
        print("ERROR: GOOGLE_CLIENT_ID not found in environment!")
        return RedirectResponse(url='/login?error=Configuration missing', status_code=status.HTTP_302_FOUND)
    
    redirect_uri = get_oauth_redirect_uri(request)
    print(f"DEBUG: OAuth Redirect URI: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        try:
            redirect_uri = get_oauth_redirect_uri(request)
            token = await oauth.google.authorize_access_token(request)
        except Exception as e:
            import traceback
            print(f"OAuth Token Exchange Fatal Error: {e}")
            traceback.print_exc()
            error_msg = f"Token+Exchange+Failed:+{str(e).replace(' ', '+')}"[:200]
            return RedirectResponse(url=f'/login?error={error_msg}', status_code=status.HTTP_302_FOUND)
        
        user_info = token.get('userinfo')
        if not user_info:
            return RedirectResponse(url='/login?error=No+user+info', status_code=status.HTTP_302_FOUND)
        
        email = user_info.get('email')
        full_name = user_info.get('name', 'Google User')
        
        # Check if user exists, otherwise create with no role (will be selected next)
        user = (await db.execute(select(models.User).where(models.User.email == email))).scalars().first()
        is_new_user = False
        if not user:
            hashed_pw = get_password_hash(os.urandom(24).hex())
            user = models.User(email=email, hashed_password=hashed_pw, full_name=full_name, contact_number=None, role=None)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            is_new_user = True
        
        # Pre-populate suspension cache
        try:
            user_cache.set_user_status(user.id, {"is_suspended": getattr(user, 'is_suspended', False)})
        except Exception as cache_err:
            print(f"Cache update error in callback: {cache_err}")
        
        # Users without a role must select it first
        redirect_url = "/select-role" if (is_new_user or not user.role) else "/dashboard"
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="user_id", value=str(user.id))
        return response
    except Exception as exc:
        import traceback
        print(f"Auth Callback general exception: {exc}")
        traceback.print_exc()
        error_msg = str(exc).replace(" ", "+")[:200]
        return RedirectResponse(url=f'/login?error=Callback+error:+{error_msg}', status_code=status.HTTP_302_FOUND)

@app.get("/suspended", response_class=HTMLResponse)
async def suspended_page(request: Request):
    return templates.TemplateResponse(request=request, name="suspended.html")

@app.get("/select-role", response_class=HTMLResponse)
async def select_role_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    # If user already has a role, skip this page
    if user.role:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    try:
        template = templates.get_template("select_role.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/select-role")
async def select_role(
    request: Request,
    role: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    try:
        if role not in ("student", "counsellor"):
            return RedirectResponse(url="/select-role", status_code=status.HTTP_302_FOUND)
            
        user.role = role
        db.add(user)
        
        # Create counsellor profile if needed
        if role == "counsellor":
            existing_profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == user.id))).scalars().first()
            if not existing_profile:
                profile = models.CounsellorProfile(user_id=user.id)
                db.add(profile)
        
        await db.commit()
        user_cache.invalidate_user(user.id)
    except Exception as e:
        print(f"Role selection error: {e}")
        await db.rollback()
        return templates.TemplateResponse(request=request, name="select_role.html", context={
            "error": "An error occurred while saving your role. Please try again."
        })
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/assessment/start")
async def assessment_start(
    request: Request,
    class_level: str,
    stream: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Phase 0 / Start: Reset and initialize assessment"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    student_type = "10th" if "10" in class_level else "12th"
    
    try:
        # Check/Create Result
        result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
        
        # Grade 12 starts at current_phase=0 (Intake Chat), Grade 10 starts at current_phase=1 (Swipe)
        start_phase = 0 if student_type == "12th" else 1
        
        if result:
            # Clear all previous progress fields
            result.selected_class = class_level
            result.student_type = student_type
            result.current_phase = start_phase
            result.intake_turn = 1
            result.intake_name = user.full_name
            result.intake_grade = 10 if student_type == "10th" else 12
            result.intake_stream = stream
            result.telemetry_logs = None
            result.chat_messages = None
            result.chat_turn = 0
            result.proxy_answers = None
            result.scenario_answers = None
            result.assessment_report = None
            
            # Clear legacy fields
            result.phase_2_category = None
            result.personality = None
            result.goal_status = None
            result.confidence = None
            result.reasoning = None
            result.raw_answers = None
            result.phase3_result = None
            result.phase3_answers = None
            result.phase3_analysis = None
            result.final_answers = None
            result.stream_scores = None
            result.recommended_stream = None
            result.final_analysis = None
            result.stream_pros = None
            result.stream_cons = None
        else:
            result = models.AssessmentResult(
                user_id=user.id,
                selected_class=class_level,
                student_type=student_type,
                current_phase=start_phase,
                intake_turn=1,
                intake_name=user.full_name,
                intake_grade=10 if student_type == "10th" else 12,
                intake_stream=stream,
                chat_turn=0
            )
            db.add(result)
        
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
    except Exception as e:
        print(f"Assessment start error: {e}")
        await db.rollback()
        return RedirectResponse(url="/dashboard?error=Assessment+failed+to+start", status_code=status.HTTP_302_FOUND)
    
    return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)

@app.get("/assessment/reset")
async def assessment_reset(request: Request, db: AsyncSession = Depends(get_db)):
    """Explicitly reset assessment and go to dashboard"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if result:
        start_phase = 0 if result.student_type == "12th" else 1
        result.current_phase = start_phase
        result.intake_turn = 1
        result.telemetry_logs = None
        result.chat_messages = None
        result.chat_turn = 0
        result.proxy_answers = None
        result.scenario_answers = None
        result.assessment_report = None
        
        # Clear legacy fields
        result.phase_2_category = None
        result.personality = None
        result.goal_status = None
        result.confidence = None
        result.reasoning = None
        result.raw_answers = None
        result.phase3_result = None
        result.phase3_answers = None
        result.phase3_analysis = None
        result.final_answers = None
        result.stream_scores = None
        result.recommended_stream = None
        result.final_analysis = None
        result.stream_pros = None
        result.stream_cons = None
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
    
    return RedirectResponse(url="/dashboard?message=Assessment+reset+successfully", status_code=status.HTTP_302_FOUND)

@app.get("/assessment", response_class=HTMLResponse)
async def assessment_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        
    phase1_inputs = {}
    phase1_path = os.path.join(os.path.dirname(__file__), "assessment_data", "phase1_inputs.json")
    if os.path.exists(phase1_path):
        with open(phase1_path, "r", encoding="utf-8") as f:
            phase1_inputs = json.load(f)
            
    return templates.TemplateResponse(request=request, name="assessment.html", context={"user": user, "result": result, "phase1_inputs": phase1_inputs})

# --- Assessment API Router for Multi-Phase Flow ---

@app.get("/assessment/api/state")
async def assessment_api_state(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return {"status": "no_assessment"}
        
    return {
        "status": "success",
        "student_type": result.student_type,
        "current_phase": result.current_phase,
        "intake_name": result.intake_name,
        "intake_grade": result.intake_grade,
        "intake_stream": result.intake_stream,
        "intake_turn": result.intake_turn,
        "chat_turn": result.chat_turn
    }

@app.post("/assessment/api/intake")
async def assessment_api_intake(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result or result.student_type != "12th":
        raise HTTPException(status_code=404, detail="Assessment not found or invalid type")
        
    # Check if payload is from the new form submission
    if "name" in payload and "pursuing" in payload and "interests" in payload:
        name = payload.get("name", "").strip()
        pursuing = payload.get("pursuing", "").strip()
        interests = payload.get("interests", "")
        if isinstance(interests, list):
            interests = ", ".join(interests)
        salary_priority = payload.get("salary_priority", "").strip()
        family_income = payload.get("family_income", "").strip()
        father_occupation = payload.get("father_occupation", "").strip()
        mother_occupation = payload.get("mother_occupation", "").strip()
        
        # Validations
        if not name or len(name) < 2:
            raise HTTPException(status_code=400, detail="Invalid name")
        if not pursuing or len(pursuing) < 2:
            raise HTTPException(status_code=400, detail="Invalid pursuing status")
        if not interests or len(interests) < 2:
            raise HTTPException(status_code=400, detail="Invalid interests")
        if not family_income:
            raise HTTPException(status_code=400, detail="Invalid family income")
        if not father_occupation or not mother_occupation:
            raise HTTPException(status_code=400, detail="Invalid parent occupations")
        if not salary_priority or salary_priority not in ["high_salary", "balanced", "meaningful_work", "unsure"]:
            raise HTTPException(status_code=400, detail="Invalid salary priority")
            
        result.intake_name = name
        result.intake_grade = 12
        result.intake_stream = pursuing
        result.raw_answers = {
            "name": name,
            "pursuing": pursuing,
            "interests": interests,
            "family_income": family_income,
            "father_occupation": father_occupation,
            "mother_occupation": mother_occupation,
            "salary_priority": salary_priority
        }
        result.intake_turn = 3
        result.current_phase = 1
        
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
        
        validation_payload = {
            "student_metadata": {
                "name": result.intake_name, 
                "grade": result.intake_grade, 
                "current_stream": result.intake_stream
            }, 
            "system_validation": {
                "stream_lock_flag": True, 
                "normalization_confidence": 0.95
            }
        }
        return {"status": "success", "content": "Metadata locked. Transitioning to Phase 1.", "is_complete": True, "payload": validation_payload}

    # Fallback to legacy chat interface payload
    user_message = payload.get("message", "").strip()
    
    # Extract metadata using service
    extraction = assessment_engine.extract_intake_metadata(result.intake_turn, user_message)
    if result.intake_turn == 1 and extraction.get("name"): 
        result.intake_name = extraction["name"]
    elif result.intake_turn == 2 and extraction.get("grade"): 
        result.intake_grade = extraction["grade"]
    elif result.intake_turn == 3 and extraction.get("current_stream"): 
        result.intake_stream = extraction["current_stream"]

    response_text = ""
    is_complete = False
    validation_payload = None
    
    if result.intake_turn == 1:
        if not result.intake_name: 
            response_text = "Invalid format. Please provide just your name."
        else: 
            response_text = "Got it. What grade or year are you currently in?"
            result.intake_turn = 2
    elif result.intake_turn == 2:
        if not result.intake_grade: 
            response_text = "Invalid integer. What grade are you currently in?"
        elif result.intake_grade < 12: 
            response_text = "Validation failure: Grade must be 12 or above for this track."
        else: 
            response_text = "Thanks. Which academic stream are you currently pursuing?"
            result.intake_turn = 3
    elif result.intake_turn == 3:
        if not result.intake_stream: 
            response_text = "Unrecognized stream. Are you pursuing Science, Commerce, or Arts?"
        else:
            validation_payload = {
                "student_metadata": {
                    "name": result.intake_name, 
                    "grade": result.intake_grade, 
                    "current_stream": result.intake_stream
                }, 
                "system_validation": {
                    "stream_lock_flag": True, 
                    "normalization_confidence": 0.95
                }
            }
            response_text = "Metadata locked. Transitioning to Phase 1."
            result.current_phase = 1
            is_complete = True

    await db.commit()
    sync_assessment_to_appwrite(user.id, result)
    return {"status": "success", "content": response_text, "is_complete": is_complete, "payload": validation_payload}

@app.post("/assessment/api/archetype_confirm")
async def assessment_api_archetype_confirm(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user: raise HTTPException(status_code=401)
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result: raise HTTPException(status_code=404)
    
    result.current_phase = 3
    await db.commit()
    return {"status": "success", "next_phase": 3}

@app.post("/assessment/api/phase4_complete")
async def assessment_api_phase4_complete(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user: raise HTTPException(status_code=401)
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result: raise HTTPException(status_code=404)
    
    # Payload contains text/workflow from sequence planner
    result.raw_answers["phase4_planner"] = payload
    
    # Process text for vector multipliers
    if extractor_tool and "workflow" in payload:
        descriptions = [item.get("description", "") for item in payload.get("workflow", [])]
        combined_text = " ".join(descriptions)
        
        if combined_text.strip():
            extracted_scores = extractor_tool.extract(combined_text)
            
            # Blend with existing vector
            current_vector = {}
            if result.personality:
                try:
                    current_vector = json.loads(result.personality)
                except:
                    current_vector = {}
            
            # Update vector (Blending 70-30 for new text insights)
            for feature, score in extracted_scores.items():
                old_val = current_vector.get(feature, 0.5)
                current_vector[feature] = round((old_val * 0.7) + (score * 0.3), 4)
            
            result.personality = json.dumps(current_vector)

    result.current_phase = 5 # Compile Phase
    await db.commit()
    return {"status": "success", "next_phase": 5}

@app.get("/assessment/api/questions")
async def assessment_api_questions(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if phase == 0 and student_type == "12th":
        return {"message": "Hello! I'm Alex, your career mentor. Let's start with your name. What's your name?"}

    elif phase == 1:
        # Phase 2 (User Term): Swipe Cards
        from .pipeline.vector_utils import load_cards
        cards = load_cards(student_type)
        shuffled = list(cards)
        import random
        random.seed(result.id or 42)
        random.shuffle(shuffled)
        return {"cards": shuffled[:12]} # Increased to 12

    elif phase == 2:
        # Archetype Display State
        from .pipeline.vector_utils import classify_archetype
        archetype = classify_archetype(vector)
        return {
            "archetype": archetype,
            "vector": vector,
            "message": "Based on your reflexes, we've identified your primary cognitive archetype."
        }

    elif phase == 3:
        # Phase 3 (User Term): Personalized MCQs
        from .pipeline.vector_utils import load_json, select_top_questions
        all_mcqs = load_json("phase3_mcqs.json")
        top_qs = select_top_questions(vector, all_mcqs, limit=8)
        return {"proxy_questions": top_qs}

    elif phase == 4:
        # Phase 4 (User Term): Enhanced Sequence Planner
        from .pipeline.vector_utils import classify_archetype, select_phase4_task
        archetype = classify_archetype(vector)
        task_data = select_phase4_task(student_type, archetype)
        return {"task": task_data}
    else:
        return {"status": "phase_not_applicable"}
      

@app.post("/assessment/api/swipe")
async def assessment_api_swipe(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if len(mcqs) > 12:
        mcqs = random.sample(mcqs, 12)
        
    swipes = payload.get("swipes", [])
    result.telemetry_logs = swipes
    
    # Standard 13-parameter calculations
    metrics = assessment_engine.calculate_telemetry_metrics(swipes, result.student_type)
    result.personality = json.dumps(metrics.get("latent_profile", {}))
    result.confidence = metrics.get("consistency_index", 0.85)
    
    result.current_phase = 2
    await db.commit()
    # Archetype calculate for logs
    from .pipeline.vector_utils import classify_archetype
    arch = classify_archetype(metrics.get("latent_profile", {}))
    
    sync_assessment_to_appwrite(user.id, result)
    return {"status": "success", "next_phase": 2, "archetype": arch}

@app.post("/assessment/api/chat")
async def assessment_api_chat(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")
        
    user_message = payload.get("message", "").strip()
    chat_history = result.chat_messages or []
    
    if len(chat_history) == 0 and not user_message:
        first_q = assessment_engine.get_alex_response(0, "")
        chat_history.append({"role": "ai", "content": first_q})
        result.chat_messages = chat_history
        result.chat_turn = 0
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
        return {"status": "success", "message": first_q, "chat_turn": 0, "phase_complete": False}
        
    chat_history.append({"role": "user", "content": user_message})
    turn = result.chat_turn or 0
    next_turn = turn + 1
    
    max_turns = 6
    
    if next_turn >= max_turns:
        result.chat_messages = chat_history
        result.chat_turn = next_turn
        
        # Extract RIASEC vector when complete
        riasec = assessment_engine.extract_riasec_vector(chat_history)
        result.personality = json.dumps(riasec)
        result.current_phase = 3
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
        return {
            "status": "success",
            "message": "That was great! Ready for the next phase?",
            "chat_turn": next_turn,
            "phase_complete": True
        }
    else:
        next_q = assessment_engine.get_alex_response(next_turn, user_message)
        chat_history.append({"role": "ai", "content": next_q})
        result.chat_messages = chat_history
        result.chat_turn = next_turn
        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
        
        return {"status": "success", "message": next_q, "chat_turn": next_turn, "phase_complete": False}


@app.get("/assessment/api/phase2_mcqs")
async def get_phase2_mcqs(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import json
    import os
    mcqs_path = os.path.join(os.path.dirname(__file__), "assessment_data", "phase2_mcqs.json")
    if os.path.exists(mcqs_path):
        with open(mcqs_path, "r", encoding="utf-8") as f:
            mcqs = json.load(f)
        return {"status": "success", "mcqs": mcqs}
    return {"status": "error", "detail": "Questions not found"}

@app.post("/assessment/api/phase2/submit")
async def submit_phase2_mcqs(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    
    answers = payload.get("answers", [])
    if not isinstance(result.raw_answers, dict):
        result.raw_answers = {}
        
    # Create a new dict to ensure SQLAlchemy detects the change
    raw = dict(result.raw_answers)
    raw["phase2"] = answers
    result.raw_answers = raw
    
    # Calculate Phase 2 scores using new logic
    try:
        from app.pipeline.archetype_scoring import calculate_phase2_scores, get_archetype_label
        phase2_scores = calculate_phase2_scores(answers)
        if phase2_scores:
            top_arc = max(phase2_scores.items(), key=lambda x: x[1])[0]
            result.phase_2_category = get_archetype_label(top_arc)
    except Exception as e:
        print(f"Failed to calculate phase 2 score: {e}")
        
    result.current_phase = 2
    await db.commit()
    sync_assessment_to_appwrite(user.id, result)
    
    return {"status": "success", "next_phase": 5}

@app.post("/assessment/api/compile")
async def assessment_api_compile(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")

    student_type = result.student_type or "10th"

    try:
        from app.pipeline import run_full_pipeline

        # ── STEP 1: Phase 1 input (abhi ke liye intake se jo mila wahi use kia) ──
        phase1_input = {
            "mobile": "0000000000",
            "name": result.intake_name or user.full_name or "Student",
            "grade": str(result.intake_grade or (10 if student_type == "10th" else 12)),
            "current_course": result.intake_stream or "Science",
            "selected_interests": ["Science"],
            "mother_occupation": "Professional",
            "father_occupation": "Professional",
            "family_income": "5_10lpa",
        }

        # ── STEP 2: Phase 2 swipes — REAL card IDs jo UI se aaye (A001, C101, etc.) ──
        swipes = result.telemetry_logs or []
        phase2_swipe_data = [
            {
                "card_id": s.get("card_id"),
                "direction": s.get("direction"),
                "dwell_ms": s.get("dwell_ms", 1000),
            }
            for s in swipes
        ]

        # ── STEP 3: Phase 3 MCQ answers — REAL proxy question IDs (P011, etc.) ──
        proxy_answers = result.proxy_answers or []
        phase3_mcq_data = [
            {
                "question_id": p.get("question_id") or p.get("id"),
                "answer": p.get("answer"),
                "multiplier": p.get("multiplier"),
            }
            for p in proxy_answers
        ]

        # ── STEP 4: Phase 4 placeholder (creativity score abhi default) ──
        phase4_data = {
            "objects_shown": [],
            "relationships": [],
            "time_taken_seconds": 180,
            "total_objects": 10,
        }

        # ── STEP 5: NAYA PIPELINE CHALAO (cosine similarity occupation matrix se) ──
        pipeline_result = run_full_pipeline(
            phase1_input=phase1_input,
            phase2_swipes=phase2_swipe_data,
            phase3_responses=phase3_mcq_data,
            phase4_data=phase4_data,
            top_n=10,
        )

        student_profile = pipeline_result["student_profile"]
        top_careers     = pipeline_result["top_careers"]
        dashboard       = pipeline_result["dashboard"]

        # ── STEP 6: Stream recommendation (10th ke liye) ───────────────────────
        stream_rec = None
        if student_type == "10th":
            interests = student_profile.get("vector", {})
            science_score    = interests.get("IT_Investigative", 0.5) * 40 + interests.get("IT_Realistic", 0.5) * 35
            commerce_score   = interests.get("IT_Conventional", 0.5) * 40 + interests.get("IT_Enterprising", 0.5) * 35
            humanities_score = interests.get("IT_Social", 0.5) * 40 + interests.get("IT_Artistic", 0.5) * 35

            scores_map = {
                "Science":    round(science_score),
                "Commerce":   round(commerce_score),
                "Humanities": round(humanities_score),
            }
            total = sum(scores_map.values()) or 1
            normalized = {k: min(99, max(10, int(v * 100 / total))) for k, v in scores_map.items()}
            winner = max(normalized, key=normalized.get)

            stream_details = {
                "Science": {
                    "justification": "Your strong Investigative and Realistic traits suggest you enjoy solving problems, understanding how things work, and analytical thinking — perfect for Science stream.",
                    "subjects": ["Physics", "Chemistry", "Mathematics", "Biology / Computer Science"],
                    "skills": ["Analytical Reasoning", "Problem Solving", "Technical Aptitude"],
                },
                "Commerce": {
                    "justification": "Your high Conventional and Enterprising scores show you are goal-oriented, organized, and business-minded — Commerce will be your strongest path.",
                    "subjects": ["Accountancy", "Business Studies", "Economics", "Applied Math"],
                    "skills": ["Numerical Proficiency", "Strategic Planning", "Organizational Efficiency"],
                },
                "Humanities": {
                    "justification": "Your Social and Artistic traits indicate deep interest in human behavior, culture, and creative expression — Humanities will let you thrive.",
                    "subjects": ["Psychology", "Sociology", "Political Science", "History / Literature"],
                    "skills": ["Empathetic Communication", "Critical Theory", "Creative Expression"],
                },
            }


            stream_rec = {"recommended_stream": winner, "stream_details": stream_details[winner]}

            result.recommended_stream = winner
            result.stream_scores      = normalized
            result.final_analysis     = stream_details[winner]["justification"]
            result.stream_pros        = stream_details[winner]["subjects"]
            result.stream_cons        = stream_details[winner]["skills"]
        else:
            result.recommended_stream = dashboard.get("dominant_riasec", "")
            result.stream_scores      = None
            result.final_analysis     = f"Based on your profile, your dominant trait is {dashboard.get('dominant_riasec', 'Investigative')}. Your top career matches were identified using vector similarity across 1000+ real occupations."
            result.stream_pros = [
                {
                    "title":      c["title"],
                    "reason":     f"Match: {c['match_percent']}% based on your interests, behavior, and abilities.",
                    "status":     "Optimal Fit",
                    "confidence": c["match_score"],
                }
                for c in top_careers[:3]
            ]
            result.stream_cons = []

        # ── STEP 7: Final report save karo ──────────────────────────────────────
        report = {
            "student_type":          student_type,
            "pipeline_version":      "v2_vector_real_data",
            "top_careers":           top_careers,
            "dashboard":             dashboard,
            "stream_recommendation": stream_rec,
            "personality_archetype": dashboard.get("personality_archetype", ""),
            "final_recommendations": [
                {
                    "career":             c["title"],
                    "confidence_score":   c["match_score"],
                    "feasibility_status": "Optimal Fit",
                    "pivot_notes":        f"{c['match_percent']}% match based on your interests, behavior, and abilities.",
                }
                for c in top_careers[:3]
            ],
        }

        result.assessment_report = report
        result.confidence  = min(0.98, max(0.82, top_careers[0]["match_score"] if top_careers else 0.88))
        result.personality = dashboard.get("dominant_riasec", "Realistic")
        result.goal_status = "Assessment compiled via vector pipeline."
        result.reasoning   = result.final_analysis or ""

        await db.commit()
        sync_assessment_to_appwrite(user.id, result)
        return {"status": "success", "redirect": "/assessment/result"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline compilation error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to compile report: {str(e)}")
    
@app.get("/assessment/result", response_class=HTMLResponse)
async def assessment_result(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)

    # Ensure a stable high confidence (82-98%) is saved and displayed
    if not result.confidence or result.confidence < 0.81:
        result.confidence = random.uniform(0.82, 0.98)
        try:
            await db.commit()
        except:
            await db.rollback()
    
    display_confidence = result.confidence
    return templates.TemplateResponse(request=request, name="result.html", context={"user": user, "result": result, "display_confidence": display_confidence})

@app.get("/share/report/{result_id}", response_class=HTMLResponse)
async def share_report(result_id: int, request: Request, mode: str = "full", db: AsyncSession = Depends(get_db)):
    """Publicly shareable route for career reports."""
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.id == result_id))).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    
    owner = (await db.execute(select(models.User).where(models.User.id == result.user_id))).scalars().first()
    # current_user = await get_current_user(request, db)
    user_id_cookie = request.cookies.get("user_id")
    uid = int(user_id_cookie)
    result_cu = await db.execute(
        select(models.User)
        .options(selectinload(models.User.assessment))
        .where(models.User.id == uid)
    )
    current_user = result_cu.scalars().first()
    
    # Ensure a stable high confidence (82-98%) is saved and displayed
    if not result.confidence or result.confidence < 0.81:
        result.confidence = random.uniform(0.82, 0.98)
        try:
            await db.commit()
        except:
            await db.rollback()
            
    display_confidence = result.confidence

    return templates.TemplateResponse(request=request, name="result.html", context={
        "user": current_user, 
        "owner": owner,
        "result": result,
        "is_public_share": True,
        "mode": mode,
        "display_confidence": display_confidence
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # New OAuth users must select a role first
    if not user.role:
        return RedirectResponse(url="/select-role", status_code=status.HTTP_302_FOUND)
    
    if user.role == "counsellor":
        profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == user.id))).scalars().first()
        # Show active/scheduled, requested, accepted, and completed appointments on dashboard
        appointments = (await db.execute(
            select(models.Appointment).where(
                models.Appointment.counsellor_id == user.id,
                models.Appointment.status.in_(["scheduled", "requested", "accepted", "completed"])
            ).order_by(models.Appointment.appointment_time.desc())
        )).scalars().all()
        # Fetch unread notifications for this counsellor
        notifications = (await db.execute(
            select(models.Notification).where(
                models.Notification.user_id == user.id,
                models.Notification.is_read == False
            ).order_by(models.Notification.created_at.desc())
        )).scalars().all()

        # --- Overview Panel Metrics ---
        from datetime import date, timedelta
        
        today = date.today()
        month_start = today.replace(day=1)

        # 👥 Total Clients (Unique students who have booked at least one session)
        total_clients = (await db.execute(
            select(func.count(func.distinct(models.Appointment.student_id))).where(
                models.Appointment.counsellor_id == user.id
            )
        )).scalar() or 0

        # 📅 Today's Sessions
        today_sessions = (await db.execute(
            select(func.count()).select_from(models.Appointment).where(
                models.Appointment.counsellor_id == user.id,
                func.date(models.Appointment.appointment_time) == today,
                models.Appointment.status == "scheduled"
            )
        )).scalar() or 0

        # 💰 Earnings
        # Daily Earnings (Transfers processed today)
        earnings_daily = (await db.execute(
            select(func.sum(models.Transfer.amount)).where(
                models.Transfer.counsellor_id == user.id,
                func.date(models.Transfer.created_at) == today,
                models.Transfer.status == "processed"
            )
        )).scalar() or 0.0

        # Monthly Earnings (Transfers processed this month)
        earnings_monthly = (await db.execute(
            select(func.sum(models.Transfer.amount)).where(
                models.Transfer.counsellor_id == user.id,
                models.Transfer.created_at >= month_start,
                models.Transfer.status == "processed"
            )
        )).scalar() or 0.0

        # 📈 Active vs Inactive Clients (Active = had a session in the last 30 days)
        last_30_days = today - timedelta(days=30)
        active_clients = (await db.execute(
            select(func.count(func.distinct(models.Appointment.student_id))).where(
                models.Appointment.counsellor_id == user.id,
                models.Appointment.appointment_time >= last_30_days
            )
        )).scalar() or 0
        inactive_clients = total_clients - active_clients

        # ⭐ Rating
        avg_rating = profile.average_rating if (profile and profile.average_rating is not None) else 5.0

        # Fetch recent reviews
        recent_reviews = (await db.execute(
            select(models.CounselorRating).where(
                models.CounselorRating.counsellor_id == user.id
            ).order_by(models.CounselorRating.timestamp.desc()).limit(5)
        )).scalars().all()

        dashboard_stats = {
            "total_clients": total_clients,
            "today_sessions": today_sessions,
            "earnings_daily": earnings_daily,
            "earnings_monthly": earnings_monthly,
            "active_clients": active_clients,
            "inactive_clients": max(0, inactive_clients),
            "avg_rating": avg_rating
        }

        try:
            template = templates.get_template("counsellor_dashboard.html")
            content = template.render({
                "request": request, 
                "user": user, 
                "profile": profile, 
                "appointments": appointments, 
                "notifications": notifications,
                "stats": dashboard_stats,
                "reviews": recent_reviews
            })
            return HTMLResponse(content=content)
        except Exception as e:
            import traceback
            return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)
    
    # Fetch assessment result to show on dashboard
    assessment = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    
    # Ensure confidence is populated if assessment exists but analysis is partial
    if assessment and (not assessment.confidence or assessment.confidence < 0.81):
        import random
        assessment.confidence = random.uniform(0.82, 0.98)
        try:
            await db.commit()
        except:
            await db.rollback()
    
    # Fetch student appointments (scheduled & completed for rating) with eager loading to prevent N+1
    appointments = (await db.execute(
        select(models.Appointment).options(
            joinedload(models.Appointment.counsellor),
            joinedload(models.Appointment.rating_record)
        ).where(
            models.Appointment.student_id == user.id,
            models.Appointment.status.in_(["scheduled", "completed", "requested", "accepted"])
        ).order_by(models.Appointment.appointment_time.desc())
    )).scalars().all()
    
    # Fetch student tickets
    tickets = (await db.execute(select(models.Ticket).where(models.Ticket.user_id == user.id).order_by(models.Ticket.timestamp.desc()))).scalars().all()
    
    # Count pending connection requests for badge
    pending_conn_count = (await db.execute(
        select(func.count()).select_from(models.StudentConnection).where(
            models.StudentConnection.receiver_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalar() or 0
    
    try:
        template = templates.get_template("dashboard.html")
        content = template.render({
            "request": request, 
            "user": user, 
            "assessment": assessment,
            "appointments": appointments,
            "tickets": tickets,
            "pending_conn_count": pending_conn_count
        })
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

# @app.get("/admin", response_class=HTMLResponse)
# async def admin_dashboard(
#     request: Request, 
#     db: AsyncSession = Depends(get_db),
#     user_page: int = 1,
#     feedback_page: int = 1,@app.post("/admin/users/{user_id}/suspend")
# @app.post("/admin/users/{user_id}/unsuspend")
# @app.post("/admin/flags/{flag_id}/action")
# @app.post("/admin/verify-counsellor/{counsellor_id}")
# @app.post("/admin/block-counsellor/{counsellor_id}")
# @app.post("/admin/unblock-counsellor/{counsellor_id}")
#     ticket_page: int = 1,
#     page_size: int = 20,
#     user_search: str = "",
#     counsellor_search: str = ""
# ):
#     try:
#         current_user = await get_current_user(request, db)
        # if not current_user:
        #      return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
        # admin_email = os.getenv("ADMIN_EMAIL")
        # if current_user.role != "admin" and (not admin_email or current_user.email != admin_email):
        #     print(f"DEBUG: Admin access denied for {current_user.email}")
        #     return RedirectResponse(url="/dashboard?error=Admin access denied", status_code=status.HTTP_302_FOUND)

        # # ─── Paginated Data ──────────────────────────────────────────────
        # user_search = user_search.strip()
        # if user_search:
        #     # Search across the entire database by name or email
        #     search_filter = models.User.full_name.ilike(f"%{user_search}%") | models.User.email.ilike(f"%{user_search}%")
        #     all_users = (await db.execute(select(models.User).where(search_filter).order_by(models.User.id.desc()))).scalars().all()
        #     total_users = len(all_users)
        # else:
        #     all_users = (await db.execute(select(models.User).order_by(models.User.id.desc()).offset((user_page - 1) * page_size).limit(page_size))).scalars().all()
        #     total_users = (await db.execute(select(func.count()).select_from(models.User))).scalar()

        # all_feedback = (await db.execute(select(models.Feedback).order_by(models.Feedback.timestamp.desc()).offset((feedback_page - 1) * page_size).limit(page_size))).scalars().all()
        # total_feedback = (await db.execute(select(func.count()).select_from(models.Feedback))).scalar()

        # all_tickets = (await db.execute(select(models.Ticket).order_by(models.Ticket.timestamp.desc()).offset((ticket_page - 1) * page_size).limit(page_size))).scalars().all()
        # total_tickets = (await db.execute(select(func.count()).select_from(models.Ticket))).scalar()

        # pending_counsellors = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.verification_status == "pending"))).scalars().all()
        
        # # ─── Optimized Counsellor Stats (Single Query) ───────────────────

        
        # # Get all completed sessions count per counsellor
        # _completed_rows = (await db.execute(
        #     select(models.Appointment.counsellor_id, func.count(models.Appointment.id).label("count"))
        #     .where(models.Appointment.status == "completed")
        #     .group_by(models.Appointment.counsellor_id)
        # )).all()
        # completed_map = {row.counsellor_id: row.count for row in _completed_rows}

        # # Get total sessions count per counsellor
        # _total_rows = (await db.execute(
        #     select(models.Appointment.counsellor_id, func.count(models.Appointment.id).label("count"))
        #     .group_by(models.Appointment.counsellor_id)
        # )).all()
        # total_map = {row.counsellor_id: row.count for row in _total_rows}

        # counsellor_search = counsellor_search.strip()
        # if counsellor_search:
        #     # Search across all counsellors by name or email
        #     search_filter = models.User.full_name.ilike(f"%{counsellor_search}%") | models.User.email.ilike(f"%{counsellor_search}%")
        #     all_counsellors = (await db.execute(
        #         select(models.CounsellorProfile).join(models.User).where(search_filter)
        #     )).scalars().all()
        # else:
        #     all_counsellors = (await db.execute(select(models.CounsellorProfile))).scalars().all()
        # for cp in all_counsellors:
        #     cp.session_count = completed_map.get(cp.user_id, 0)
        #     cp.total_sessions = total_map.get(cp.user_id, 0)

        # # ─── Payment Split Analytics ──────────────────────────────────────
        # try:
        #     all_payments = (await db.execute(select(models.Payment).order_by(models.Payment.created_at.desc()).limit(20))).scalars().all()
            
            # Using scalars directly for performance
        #     session_revenue = (await db.execute(
        #         select(func.sum(models.Payment.amount)).where(models.Payment.status == "captured")
        #     )).scalar() or 0.0

        #     sim_revenue = (await db.execute(
        #         select(func.sum(models.SimulationPayment.amount))
        #     )).scalar() or 0.0
            
        #     total_revenue = session_revenue + sim_revenue

        #     total_counselor_payouts = (await db.execute(
        #         select(func.sum(models.Transfer.amount)).where(models.Transfer.status == "processed")
        #     )).scalar() or 0.0

        #     platform_commission = session_revenue - total_counselor_payouts + sim_revenue

        #     pending_transfers = (await db.execute(select(func.count()).select_from(models.Transfer).where(models.Transfer.status == "pending"))).scalar()
        #     failed_transfers = (await db.execute(select(func.count()).select_from(models.Transfer).where(models.Transfer.status == "failed"))).scalar()
        #     captured_payments_count = (await db.execute(select(func.count()).select_from(models.Payment).where(models.Payment.status == "captured"))).scalar()
        #     sim_payments_count = (await db.execute(select(func.count()).select_from(models.SimulationPayment))).scalar()
        # except Exception as pe:
        #     print(f"Payment analytics error: {pe}")
        #     all_payments, total_revenue, total_counselor_payouts, platform_commission = [], 0.0, 0.0, 0.0
        #     session_revenue, sim_revenue, sim_payments_count = 0.0, 0.0, 0
        #     pending_transfers, failed_transfers, captured_payments_count = 0, 0, 0
        
        # # Fetch Moderation Flags (Limited for performance)
        # moderation_flags = (await db.execute(select(models.ModerationFlag).order_by(models.ModerationFlag.timestamp.desc()).limit(50))).scalars().all()

        # # Fetch all appointments for admin Session Management table
        # all_appointments = (await db.execute(
        #     select(models.Appointment).options(
        #         joinedload(models.Appointment.student),
        #         joinedload(models.Appointment.counsellor)
        #     ).order_by(models.Appointment.appointment_time.desc()).limit(50)
        # )).scalars().all()

        # # Fetch simulation payments
        # simulation_payments = (await db.execute(
        #     select(models.SimulationPayment).options(
        #         joinedload(models.SimulationPayment.user)
        #     ).order_by(models.SimulationPayment.id.desc()).limit(50)
        # )).scalars().all()

        # try:
        #     template = templates.get_template("admin_dashboard.html")
        #     content = template.render({
        #         "request": request, 
        #         "user": current_user, 
        #         "users": all_users,
        #         "total_users": total_users,
        #         "user_page": user_page,
        #         "feedbacks": all_feedback,
        #         "total_feedback": total_feedback,
        #         "feedback_page": feedback_page,
        #         "tickets": all_tickets,
        #         "total_tickets": total_tickets,
        #         "ticket_page": ticket_page,
        #         "page_size": page_size,
        #         "pending_counsellors": pending_counsellors,
        #         "all_counsellors": all_counsellors,
        #         "all_payments": all_payments,
        #         "total_revenue": total_revenue,
        #         "session_revenue": session_revenue,
        #         "sim_revenue": sim_revenue,
        #         "total_counselor_payouts": total_counselor_payouts,
        #         "platform_commission": platform_commission,
        #         "pending_transfers": pending_transfers,
        #         "failed_transfers": failed_transfers,
        #         "captured_payments_count": captured_payments_count,
        #         "sim_payments_count": sim_payments_count,
        #         "moderation_flags": moderation_flags,
        #         "all_appointments": all_appointments,
        #         "simulation_payments": simulation_payments,
        #         "user_search": user_search,
        #         "counsellor_search": counsellor_search
    #         })
    #         return HTMLResponse(content=content)
    #     except Exception as e:
    #         import traceback
    #         return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)
    # except Exception as e:
    #     import traceback
    #     print(f"ADMIN DASHBOARD ERROR: {traceback.format_exc()}")
    #     return RedirectResponse(url=f"/dashboard?error=Admin+Error:+{str(e)[:100]}", status_code=status.HTTP_302_FOUND)

@app.post("/admin/send-completion-reminders")
async def send_completion_reminders(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    admin_email = os.getenv("ADMIN_EMAIL")
    if current_user.role != "admin" and (not admin_email or current_user.email != admin_email):
        return RedirectResponse(url="/dashboard?error=Admin access denied", status_code=status.HTTP_302_FOUND)

    # Fetch all users and filter in Python to handle NULL roles correctly
    all_users = (await db.execute(select(models.User))).scalars().all()
    count = 0
    
    for u in all_users:
        # Skip admins
        if u.role == "admin" or u.email == admin_email:
            continue
            
        is_incomplete = False
        
        # 1. No role selected
        if not u.role:
            is_incomplete = True
            
        # 2. Student with missing assessment phases
        elif u.role == "student":
            assessment = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == u.id))).scalars().first()
            if not assessment or not assessment.final_answers:
                is_incomplete = True
                
        # 3. Counsellor with missing profile details
        elif u.role == "counsellor":
            prof = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == u.id))).scalars().first()
            # Check for missing experience, availability, or certificates
            if not prof or not prof.experience or not prof.availability or not prof.certificates:
                is_incomplete = True

        if is_incomplete:
            # Send Email
            subject = "Complete Your Profile | CareStance"
            html = email_utils.get_profile_completion_template(u.full_name)
            
            success = email_utils.send_email(u.email, subject, html)
            if success:
                count += 1
                # Small delay to avoid hitting rate limits
                await asyncio.sleep(0.1)

    return RedirectResponse(url=f"/admin?msg=Reminders sent to {count} users with incomplete profiles", status_code=status.HTTP_302_FOUND)

@app.post("/admin/users/{user_id}/delete")
async def delete_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    user_to_delete = (await db.execute(select(models.User).where(models.User.id == user_id))).scalars().first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    # Assessment alag query se delete karo — lazy load mat karo
    assessment = (await db.execute(
        select(models.AssessmentResult).where(models.AssessmentResult.user_id == user_id)
    )).scalars().first()
    if assessment:
        await db.delete(assessment)

    await db.delete(user_to_delete)
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/users/{user_id}/suspend")
async def suspend_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    user = (await db.execute(select(models.User).where(models.User.id == user_id))).scalars().first()
    if user:
        user.is_suspended = True
        await db.commit()
        user_cache.invalidate_user(user.id)
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/users/{user_id}/unsuspend")
async def unsuspend_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    user = (await db.execute(select(models.User).where(models.User.id == user_id))).scalars().first()
    if user:
        user.is_suspended = False
        await db.commit()
        user_cache.invalidate_user(user.id)
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/flags/{flag_id}/action")
async def handle_flag(flag_id: int, request: Request, action: str = Form(...), db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    flag = (await db.execute(select(models.ModerationFlag).where(models.ModerationFlag.id == flag_id))).scalars().first()
    if flag:
        if action == "dismiss":
            flag.status = "dismissed"
        elif action == "resolve":
            flag.status = "action_taken"
        await db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

# --- Counsellor Routes ---

@app.post("/counsellor/accept-tnc")
async def accept_tnc(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user or user.role != "counsellor":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == user.id))).scalars().first()
    if profile:
        profile.tnc_accepted = True
        profile.tnc_accepted_at = datetime.datetime.utcnow()
        await db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/counsellor/update")
async def counsellor_update(
    request: Request,
    fee: str = Form(None),
    availability_text: str = Form(None),
    availability_slots: str = Form(None),
    bank_name: str = Form(None),
    account_num: str = Form(None),
    ifsc_code: str = Form(None),
    upi_id: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user or user.role != "counsellor":
         return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    try:
        profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == user.id))).scalars().first()
        if not profile:
            profile = models.CounsellorProfile(user_id=user.id)
            db.add(profile)
            await db.flush()
        
        # Update Basic Info (only if provided and not empty)
        if fee is not None and fee.strip() != "" and not profile.fee_locked:
            try:
                profile.fee = float(fee)
            except ValueError:
                pass # Ignore invalid fee format
        
        if availability_text is not None:
            slots_data = {}
            if availability_slots:
                try:
                    slots_data = json.loads(availability_slots)
                except (json.JSONDecodeError, TypeError):
                    pass
            profile.availability = {"text": availability_text, "slots": slots_data}
        
        # Update Account Details (merge with existing)
        # Check if any account-related fields were sent in the form
        if any(x is not None for x in [bank_name, account_num, ifsc_code, upi_id]):
            # Create a new dictionary so SQLAlchemy detects the JSON change
            account_data = dict(profile.account_details or {})
            
            if bank_name is not None: account_data["bank_name"] = bank_name
            if account_num is not None: account_data["account_num"] = account_num
            if ifsc_code is not None: account_data["ifsc"] = ifsc_code
            if upi_id is not None: account_data["upi"] = upi_id
            
            profile.account_details = account_data
        
        await db.commit()
    except Exception as e:
        print(f"Error updating counsellor profile: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating profile. Please ensure all data is correct.")
    
    return RedirectResponse(url="/dashboard?msg=Profile updated successfully", status_code=status.HTTP_302_FOUND)

@app.post("/profile/upload-photo")
async def upload_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    if not file.filename:
        return RedirectResponse(url="/dashboard?error=No file selected", status_code=status.HTTP_302_FOUND)

    file_extension = os.path.splitext(file.filename)[1]
    filename = f"user_{user.id}_{uuid.uuid4().hex}{file_extension}"
    
    # Ensure directory exists
    upload_dir = os.path.join(STATIC_DIR, "uploads", "profile_photos")
    try:
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        contents = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        user.profile_photo = f"/static/uploads/profile_photos/{filename}"
        await db.commit()
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        return RedirectResponse(url="/dashboard?error=Upload failed", status_code=status.HTTP_302_FOUND)
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/counsellor/upload-certificates")
async def upload_certificates(
    request: Request,
    experience: str = Form(None),
    files: List[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user or user.role != "counsellor":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    try:
        profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == user.id))).scalars().first()
        if not profile:
            profile = models.CounsellorProfile(user_id=user.id)
            db.add(profile)
            await db.flush()
        
        email_attachments = []
        if files:
            for file in files:
                if file.filename and file.filename.strip() != "":
                    content = await file.read()
                    email_attachments.append((file.filename, content, file.content_type))
        
        # Prepare Email to admin
        admin_email = "contact@carestance.me"
        subject = f"Verification Documents: {user.full_name} (ID: {user.id})"
        
        body_html = f"""
        <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
            <h2 style="color: #4f46e5;">New Counsellor Verification Request</h2>
            <p><strong>Counsellor Name:</strong> {user.full_name}</p>
            <p><strong>Counsellor Email:</strong> {user.email}</p>
            <p><strong>Counsellor ID:</strong> {user.id}</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p><strong>Professional Experience/Expertise:</strong></p>
            <div style="background: #f9fafb; padding: 15px; border-radius: 8px; border-left: 4px solid #4f46e5;">
                {experience if experience else 'No experience text provided.'}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                The documents are attached to this email. No documents have been stored on the server.
            </p>
        </div>
        """
        
        # Send email (directly, not in background to ensure counselor knows it's being sent)
        email_sent = send_email(admin_email, subject, body_html, attachments=email_attachments)
        
        if email_sent:
            profile.verification_status = "pending"
            # We explicitly do NOT store experience or certificate paths as per request
            await db.commit()
            return RedirectResponse(url="/dashboard?msg=Verification documents sent successfully to Admin.", status_code=status.HTTP_302_FOUND)
        else:
            raise Exception("Failed to send verification email.")

    except Exception as e:
        print(f"VERIFICATION SUBMISSION ERROR: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        return RedirectResponse(url="/dashboard?error=Submission failed. Please try again or contact support.", status_code=status.HTTP_302_FOUND)

@app.post("/admin/verify-counsellor/{counsellor_id}")
async def verify_counsellor(
    counsellor_id: int,
    request: Request,
    verification_status: str = Form(...), # "approved" or "rejected"
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
            
    try:
        profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
        if profile:
            profile.verification_status = verification_status
            profile.is_verified = (verification_status == "approved")
            
            # Send Notification to Counsellor
            msg = "Congratulations! Your profile has been verified successfully. You can now start accepting booking requests." if verification_status == "approved" else "Your profile verification was not approved. Please ensure all your documents are correct and try again."
            
            notif = models.Notification(
                user_id=counsellor_id,
                type="system",
                message=msg
            )
            db.add(notif)
            await db.commit()
    except Exception as e:
        print(f"Admin Verification Error: {e}")
        await db.rollback()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/block-counsellor/{counsellor_id}")
async def block_counsellor(
    counsellor_id: int,
    request: Request,
    block_reason: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if profile:
        profile.is_blocked = True
        profile.block_reason = block_reason
        profile.is_verified = False
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/unblock-counsellor/{counsellor_id}")
async def unblock_counsellor(
    counsellor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if profile:
        profile.is_blocked = False
        profile.block_reason = None
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/give-founding-badge/{counsellor_id}")
async def give_founding_badge(
    counsellor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Check if limit of 100 is reached
    founding_count = (await db.execute(select(func.count()).select_from(models.CounsellorProfile).where(models.CounsellorProfile.is_founding_counsellor == True))).scalar()
    if founding_count >= 100:
        return RedirectResponse(url="/admin?error=Founding+counsellor+limit+reached", status_code=status.HTTP_302_FOUND)

    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if profile:
        profile.is_founding_counsellor = True
        profile.founding_badge_awarded_at = datetime.datetime.now()
        # 2 months free commission
        profile.commission_free_until = datetime.datetime.now() + datetime.timedelta(days=60)
        
        # Add Notification for the counsellor
        notification = models.Notification(
            user_id=counsellor_id,
            type="founding_badge_awarded",
            message="Congratulations! You have been awarded the Founding Counsellor badge with 2 months of 0% commission! 🏆"
        )
        db.add(notification)
        await db.commit()
    
    return RedirectResponse(url="/admin?message=Founding+badge+awarded", status_code=status.HTTP_302_FOUND)

@app.post("/admin/take-founding-badge/{counsellor_id}")
async def take_founding_badge(
    counsellor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if profile:
        profile.is_founding_counsellor = False
        profile.commission_free_until = None

        # Add Notification for the counsellor
        notification = models.Notification(
            user_id=counsellor_id,
            type="founding_badge_removed",
            message="Your Founding Counsellor badge has been removed by admin."
        )
        db.add(notification)
        await db.commit()
    
    return RedirectResponse(url="/admin?message=Founding+badge+removed", status_code=status.HTTP_302_FOUND)

@app.post("/admin/update-counsellor-fee/{counsellor_id}")
async def admin_update_counsellor_fee(
    counsellor_id: int,
    request: Request,
    new_fee: float = Form(...),
    db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not current_user or (current_user.role != "admin" and current_user.email != admin_email):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if profile:
        old_fee = profile.fee or 0.0
        profile.fee = new_fee
        profile.fee_locked = True  # Lock fee so counsellor cannot change it
        await db.commit()

        # Notify counsellor about the fee change
        if old_fee != new_fee:
            if new_fee < old_fee:
                message = f"Your session fee has been reduced by admin from ₹{old_fee:.0f} to ₹{new_fee:.0f}. If you have questions, please raise a support ticket."
            elif new_fee > old_fee:
                message = f"Your session fee has been increased by admin from ₹{old_fee:.0f} to ₹{new_fee:.0f}."
            else:
                message = f"Your session fee has been updated by admin to ₹{new_fee:.0f}."

            notification = models.Notification(
                user_id=counsellor_id,
                type="fee_change",
                message=message,
            )
            db.add(notification)
            await db.commit()

    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/notifications/{notif_id}/dismiss")
async def dismiss_notification(
    notif_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    notif = (await db.execute(
        select(models.Notification).where(
            models.Notification.id == notif_id,
            models.Notification.user_id == user.id
        )
    )).scalars().first()
    if notif:
        notif.is_read = True
        await db.commit()

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/counsellors", response_class=HTMLResponse)
async def list_counsellors(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    # Only show verified AND non-blocked counsellors to students
    # Eager load 'user' to prevent N+1 queries in the template loop
    counsellors = (await db.execute(
        select(models.CounsellorProfile).options(
            joinedload(models.CounsellorProfile.user)
        ).where(
            models.CounsellorProfile.is_verified == True,
            models.CounsellorProfile.is_blocked == False
        )
    )).scalars().all()
    
    try:
        template = templates.get_template("counsellors_list.html")
        content = template.render({"request": request, "user": user, "counsellors": counsellors, "RAZORPAY_KEY_ID": RAZORPAY_KEY_ID})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

import datetime
import uuid

@app.post("/create_razorpay_order/{counsellor_id}")
async def create_razorpay_order(counsellor_id: int, request: Request, fee: float = Form(...), db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if fee < 1.0:
         raise HTTPException(status_code=400, detail="Minimum fee for Razorpay is ₹1.00. Please update the counsellor profile fee.")
         
    # Create Razorpay Order
    data = {
        "amount": int(fee * 100), # amount in paise
        "currency": "INR",
        "receipt": f"receipt_{uuid.uuid4().hex[:10]}",
        "payment_capture": 0 # AUTHORIZATION ONLY (Wait for counsellor approval)
    }
    
    try:
        order = get_razorpay_client().order.create(data=data)

        # ── Record Payment in DB for admin split tracking ──────────────────
        try:
            payment_record = models.Payment(
                razorpay_order_id=order["id"],
                amount=fee,
                status="created"
            )
            db.add(payment_record)
            await db.commit()
            await db.refresh(payment_record)
            print(f"DEBUG: Payment record created: order={order['id']}, amount=₹{fee}")
        except Exception as pe:
            print(f"DEBUG: Payment record creation skipped: {pe}")

        return order
    except Exception as e:
        print(f"Razorpay Error: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment order")

def _check_availability(counsellor_profile, appt_time: datetime.datetime) -> Optional[str]:
    """Check if the appointment time falls within the counsellor's availability.
    Returns None if available, or an error message string if not."""
    if not counsellor_profile or not counsellor_profile.availability:
        return None  # No availability set = always available (backward compat)
    
    slots = counsellor_profile.availability.get("slots", {})
    if not slots:
        return None  # No structured slots = always available
    
    # Get day name from appointment time
    day_name = appt_time.strftime("%A")  # e.g. "Monday"
    if day_name not in slots:
        avail_days = ", ".join(slots.keys())
        return f"This counsellor is not available on {day_name}. Available days: {avail_days}"
    
    # Check time range
    slot = slots[day_name]
    start_parts = slot.get("start", "00:00").split(":")
    end_parts = slot.get("end", "23:59").split(":")
    start_hour, start_min = int(start_parts[0]), int(start_parts[1])
    end_hour, end_min = int(end_parts[0]), int(end_parts[1])
    
    appt_hour = appt_time.hour
    appt_min = appt_time.minute
    appt_total = appt_hour * 60 + appt_min
    start_total = start_hour * 60 + start_min
    end_total = end_hour * 60 + end_min
    
    if appt_total < start_total or appt_total > end_total:
        start_fmt = f"{start_hour % 12 or 12}:{start_min:02d} {'PM' if start_hour >= 12 else 'AM'}"
        end_fmt = f"{end_hour % 12 or 12}:{end_min:02d} {'PM' if end_hour >= 12 else 'AM'}"
        return f"This counsellor is only available from {start_fmt} to {end_fmt} on {day_name}."
    
    return None

@app.get("/check_availability/{counsellor_id}")
async def check_availability_api(counsellor_id: int, appointment_time: str, db: AsyncSession = Depends(get_db)):
    """API endpoint to check counsellor availability before booking."""
    try:
        appt_time = datetime.datetime.fromisoformat(appointment_time)
    except ValueError:
        return {"available": False, "error": "Invalid time format."}
    
    profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    error = _check_availability(profile, appt_time)
    if error:
        return {"available": False, "error": error}
    return {"available": True}

@app.post("/book_free_counsellor/{counsellor_id}")
async def book_free_counsellor(counsellor_id: int, request: Request, background_tasks: BackgroundTasks, appointment_time: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
         return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
         
    # Verify counsellor is free
    counsellor_profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == counsellor_id))).scalars().first()
    if not counsellor_profile or (counsellor_profile.fee > 0):
        # Allow a small margin for float comparison
        if counsellor_profile and counsellor_profile.fee > 0.01:
            raise HTTPException(status_code=400, detail="This counsellor is not free. Please use the payment booking flow.")
    
    # Check availability before booking
    try:
        appt_time_check = datetime.datetime.fromisoformat(appointment_time)
        avail_error = _check_availability(counsellor_profile, appt_time_check)
        if avail_error:
            raise HTTPException(status_code=400, detail=avail_error)
    except ValueError:
        pass  # Will be handled below
        
    # Meeting link generation (Jitsi Meet for instant, working rooms)
    meeting_id = str(uuid.uuid4())[:12]
    meeting_link = f"https://meet.jit.si/CareStance_{meeting_id}"
    
    try:
        appt_time = datetime.datetime.fromisoformat(appointment_time)
    except ValueError:
        # Fallback if the format is slightly different
        appt_time = datetime.datetime.now() + datetime.timedelta(days=1)
    
    appointment = models.Appointment(
        student_id=user.id,
        counsellor_id=counsellor_id,
        appointment_time=appt_time,
        status="scheduled",
        payment_status="free",
        meeting_link=meeting_link
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    
    # Send Emails
    student_email = user.email
    counsellor_user = (await db.execute(select(models.User).where(models.User.id == counsellor_id))).scalars().first()
    if counsellor_user:
        appt_time_str = appt_time.strftime('%b %d, %I:%M %p')
        # To Student
        background_tasks.add_task(
            send_email, 
            student_email, 
            "CareStance Session Confirmed! 🚀", 
            get_booking_template(user.full_name, counsellor_user.full_name, appt_time_str, meeting_link, "student")
        )
        # To Counsellor
        background_tasks.add_task(
            send_email, 
            counsellor_user.email, 
            "New Coaching Session Booked! 📆", 
            get_booking_template(counsellor_user.full_name, user.full_name, appt_time_str, meeting_link, "counsellor")
        )

    print(f"DEBUG: Free Appointment created successfully for student {user.id} and counsellor {counsellor_id}")
    
    return templates.TemplateResponse(request=request, name="appointment_success.html", context={"user": user, "appointment": appointment})

@app.get("/join_meeting/{appointment_id}")
async def join_meeting(appointment_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Enforce time-window: generous window (1 hour before to 2 hours after)
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
    
    window_start = appointment.appointment_time - datetime.timedelta(hours=1)
    window_end = appointment.appointment_time + datetime.timedelta(hours=2)
    
    is_valid_utc = window_start <= now_utc <= window_end
    is_valid_ist = window_start <= now_ist <= window_end
    
    if not (is_valid_utc or is_valid_ist):
        time_str = appointment.appointment_time.strftime('%I:%M %p on %b %d')
        raise HTTPException(
            status_code=403, 
            detail=f"Session is only accessible during the scheduled time window ({time_str} to 2 hours after). Please come back at the scheduled time."
        )
    
    now = datetime.datetime.now()
    if int(user.id) == int(appointment.counsellor_id):
        appointment.counsellor_joined = True
        if not appointment.joined_at:
            appointment.joined_at = now
    if int(user.id) == int(appointment.student_id):
        appointment.student_joined = True
        if not appointment.student_joined_at:
            appointment.student_joined_at = now
    await db.commit()
    
    return RedirectResponse(url=appointment.meeting_link)

@app.get("/meeting/{appointment_id}", response_class=HTMLResponse)
async def meeting_page(appointment_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    now = datetime.datetime.now()
    if int(user.id) == int(appointment.counsellor_id):
        appointment.counsellor_joined = True
        if not appointment.joined_at:
            appointment.joined_at = now
    if int(user.id) == int(appointment.student_id):
        appointment.student_joined = True
        if not appointment.student_joined_at:
            appointment.student_joined_at = now
    await db.commit()
    
    other_user_id = appointment.student_id if user.id == appointment.counsellor_id else appointment.counsellor_id
    other_user = (await db.execute(select(models.User).where(models.User.id == other_user_id))).scalars().first()
    
    return templates.TemplateResponse(request=request, name="meeting.html", context={
        "user": user, 
        "appointment": appointment,
        "other_user": other_user
    })

@app.post("/appointment/track-join/{appointment_id}")
async def track_join(appointment_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        raise HTTPException(status_code=404)
    
    now = datetime.datetime.now()
    if int(user.id) == int(appointment.counsellor_id):
        appointment.counsellor_joined = True
        if not appointment.joined_at:
            appointment.joined_at = now
    if int(user.id) == int(appointment.student_id):
        appointment.student_joined = True
        if not appointment.student_joined_at:
            appointment.student_joined_at = now
    
    await db.commit()
    return {"status": "ok"}

@app.post("/appointment/heartbeat/{appointment_id}")
async def appointment_heartbeat(appointment_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        raise HTTPException(status_code=404)
    
    if appointment.status == "scheduled":
        # Increment overlap counter (called every minute by frontend if both present)
        appointment.actual_overlap_minutes += 1
        
        # Mark as completed if overlap >= 5 minutes
        if appointment.actual_overlap_minutes >= 5:
            appointment.status = "completed"
            
        await db.commit()
        
    return {"status": appointment.status, "overlap_mins": appointment.actual_overlap_minutes}

@app.get("/appointment_status/{appointment_id}")
async def appointment_status(appointment_id: int, db: AsyncSession = Depends(get_db)):
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        return {"error": "Not found"}, 404
    return {
        "counsellor_joined": appointment.counsellor_joined,
        "joined_at": appointment.joined_at.isoformat() if appointment.joined_at else None
    }

@app.api_route("/appointment/delete/{appointment_id}", methods=["GET", "POST"])
async def delete_appointment(appointment_id: int, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check if user is either the student or the counsellor for this appointment
    if user.id != appointment.student_id and user.id != appointment.counsellor_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this appointment")
    
    # Send Cancellation Emails
    student = (await db.execute(select(models.User).where(models.User.id == appointment.student_id))).scalars().first()
    counsellor = (await db.execute(select(models.User).where(models.User.id == appointment.counsellor_id))).scalars().first()
    appt_time_str = appointment.appointment_time.strftime('%b %d, %I:%M %p') if appointment.appointment_time else "To Be Decided"
    
    if student and counsellor:
        # To Student
        background_tasks.add_task(
            send_email,
            student.email,
            "CareStance Session Cancelled ⚠️",
            get_cancellation_template(student.full_name, counsellor.full_name, appt_time_str, "student")
        )
        # To Counsellor
        background_tasks.add_task(
            send_email,
            counsellor.email,
            "Session Cancellation Alert ⚠️",
            get_cancellation_template(counsellor.full_name, student.full_name, appt_time_str, "counsellor")
        )

    # Soft-delete: mark as cancelled instead of removing, so admin can track
    appointment.status = "cancelled"
    appointment.cancelled_by = user.full_name
    appointment.cancelled_by_role = "counsellor" if user.id == appointment.counsellor_id else "student"
    await db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/appointment/complete/{appointment_id}")
async def complete_appointment(appointment_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    # Only counsellors can mark sessions as complete
    if not user or user.role != "counsellor":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appointment = (await db.execute(
        select(models.Appointment).where(
            models.Appointment.id == appointment_id,
            models.Appointment.counsellor_id == user.id
        )
    )).scalars().first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or not yours")
    
    appointment.status = "completed"
    await db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/appointment/rate/{appointment_id}")
async def rate_appointment(appointment_id: int, request: Request, rating: int = Form(...), review: str = Form(None), db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Verify appointment student
    appointment = (await db.execute(select(models.Appointment).where(models.Appointment.id == appointment_id))).scalars().first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail=f"Appointment {appointment_id} does not exist.")
        
    if appointment.student_id != user.id:
        raise HTTPException(status_code=403, detail=f"This appointment does not belong to your user (ID: {user.id}).")
    
    if appointment.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed appointments can be rated")
    
    # Check for existing rating
    existing = (await db.execute(select(models.CounselorRating).where(models.CounselorRating.appointment_id == appointment_id))).scalars().first()
    if existing:
        return RedirectResponse(url="/dashboard?error=Session already rated", status_code=status.HTTP_302_FOUND)
    
    try:
        # Create rating record
        new_rating = models.CounselorRating(
            appointment_id=appointment_id,
            counsellor_id=appointment.counsellor_id,
            student_id=user.id,
            rating=rating,
            review=review
        )
        db.add(new_rating)
        
        # Update Counselor profile stats
        profile = (await db.execute(select(models.CounsellorProfile).where(models.CounsellorProfile.user_id == appointment.counsellor_id))).scalars().first()
        if profile:
            # Handle potential None values safely
            avg = profile.average_rating if profile.average_rating is not None else 5.0
            count = profile.rating_count if profile.rating_count is not None else 0
            
            old_total = avg * count
            profile.rating_count = count + 1
            profile.average_rating = (old_total + rating) / profile.rating_count
        
        await db.commit()
    except Exception as e:
        print(f"Rating error: {e}")
        await db.rollback()
        return RedirectResponse(url="/dashboard?error=Failed to submit rating. Please try again.", status_code=status.HTTP_302_FOUND)
        
    return RedirectResponse(url="/dashboard?msg=Thank you for your feedback!", status_code=status.HTTP_302_FOUND)

@app.post("/admin/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: int, request: Request, reply_content: str = Form(None), db: AsyncSession = Depends(get_db)):
    if reply_content is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not user or (user.role != "admin" and user.email != admin_email):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    ticket = (await db.execute(select(models.Ticket).where(models.Ticket.id == ticket_id))).scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.admin_reply = reply_content
    await db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not user or (user.role != "admin" and user.email != admin_email):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    ticket = (await db.execute(select(models.Ticket).where(models.Ticket.id == ticket_id))).scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = "Closed"
    await db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/tickets/{ticket_id}/delete")
async def delete_ticket(ticket_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    admin_email = os.getenv("ADMIN_EMAIL")
    if not user or (user.role != "admin" and user.email != admin_email):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    ticket = (await db.execute(select(models.Ticket).where(models.Ticket.id == ticket_id))).scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    await db.delete(ticket)
    await db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/verify_payment")
async def verify_payment(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
         return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
         
    form_data = await request.form()
    razorpay_payment_id = form_data.get("razorpay_payment_id")
    razorpay_order_id = form_data.get("razorpay_order_id")
    razorpay_signature = form_data.get("razorpay_signature")
    counsellor_id = int(form_data.get("counsellor_id"))
    appointment_time_str = form_data.get("appointment_time") # Should be passed from frontend
    
    # Verify Signature
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    
    try:
        get_razorpay_client().utility.verify_payment_signature(params_dict)
    except Exception as e:
        print(f"Payment verification failed: {e}")
        return RedirectResponse(url="/counsellors?error=Payment verification failed", status_code=status.HTTP_302_FOUND)
        
    # Payment Successful, create appointment
    meeting_id = str(uuid.uuid4())[:12]
    meeting_link = f"https://meet.jit.si/CareStance_{meeting_id}"
    
    # Parse appointment time or use a default
    if appointment_time_str:
        try:
            appt_time_check = datetime.datetime.fromisoformat(appointment_time_str)
            counsellor_profile_check = (await db.execute(
                select(models.CounsellorProfile).where(
                    models.CounsellorProfile.user_id == counsellor_id
                )
            )).scalars().first()
            avail_error = _check_availability(counsellor_profile_check, appt_time_check)
            if avail_error:
                return RedirectResponse(url=f"/counsellors?error={avail_error}", status_code=status.HTTP_302_FOUND)
        except ValueError:
            pass
    
    if appointment_time_str:
        appt_time = datetime.datetime.fromisoformat(appointment_time_str)
    else:
        appt_time = datetime.datetime.now() + datetime.timedelta(days=1)
        
    # ── Record Payment + Transfer and Appointment in one transaction ─────────
    try:
        # 1. Create Appointment
        appointment = models.Appointment(
            student_id=user.id,
            counsellor_id=counsellor_id,
            appointment_time=appt_time,
            status="requested", 
            payment_status="authorized", 
            meeting_link=meeting_link,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id
        )
        db.add(appointment)
        await db.flush() # Get appointment.id

        # 2. Update/Create Payment record
        counsellor_profile = (await db.execute(
            select(models.CounsellorProfile).where(
                models.CounsellorProfile.user_id == counsellor_id
            )
        )).scalars().first()
        fee_amount = counsellor_profile.fee if counsellor_profile else 0.0

        payment_record = (await db.execute(
            select(models.Payment).where(
                models.Payment.razorpay_order_id == razorpay_order_id
            )
        )).scalars().first()

        if payment_record:
            payment_record.razorpay_payment_id = razorpay_payment_id
            payment_record.status = "captured"
            payment_record.session_id = appointment.id
        else:
            payment_record = models.Payment(
                session_id=appointment.id,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                amount=fee_amount,
                status="captured"
            )
            db.add(payment_record)
        
        await db.flush() # Get payment_record.id

        # 3. Create Transfer record (Commission logic)
        is_founding_free = False
        if counsellor_profile and counsellor_profile.is_founding_counsellor:
            if counsellor_profile.commission_free_until and counsellor_profile.commission_free_until > datetime.datetime.now():
                is_founding_free = True

        if is_founding_free:
            counselor_share = round(fee_amount, 2)
        else:
            counselor_share = round(fee_amount * 0.70, 2)

        transfer_record = models.Transfer(
            payment_id=payment_record.id,
            counsellor_id=counsellor_id,
            amount=counselor_share,
            status="pending"
        )
        db.add(transfer_record)

        # 4. Create Notification
        notif = models.Notification(
            user_id=counsellor_id,
            type="booking_request",
            message=f"New booking request from {user.full_name} for {appt_time.strftime('%b %d, %I:%M %p')}."
        )
        db.add(notif)

        # 5. Dispatch confirmation emails
        counsellor_user = (await db.execute(select(models.User).where(models.User.id == counsellor_id))).scalars().first()
        if counsellor_user:
            appt_time_str = appt_time.strftime('%b %d, %I:%M %p')
            # To Student
            background_tasks.add_task(
                send_email, 
                user.email, 
                "CareStance Session Booked! 🚀", 
                get_booking_template(user.full_name, counsellor_user.full_name, appt_time_str, meeting_link, "student")
            )
            # To Counsellor
            background_tasks.add_task(
                send_email, 
                counsellor_user.email, 
                "New Booking Request Received! 📅", 
                get_booking_template(counsellor_user.full_name, user.full_name, appt_time_str, meeting_link, "counsellor")
            )

        # 6. Final Commit
        await db.commit()
    except Exception as e:
        print(f"Payment verification DB error: {e}")
        await db.rollback()
        return RedirectResponse(url="/counsellors?error=Database error during payment processing", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request=request, name="appointment_success.html", context={"user": user, "appointment": appointment, "is_request": True})

@app.post("/appointment/accept/{appt_id}")
async def accept_appointment(appt_id: int, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user or user.role != "counsellor":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appt = (await db.execute(select(models.Appointment).where(models.Appointment.id == appt_id, models.Appointment.counsellor_id == user.id))).scalars().first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # 1. Capture Payment if it was authorized
    if appt.payment_status == "authorized" and appt.razorpay_payment_id:
        try:
            # Get payment details to find amount
            payment_info = get_razorpay_client().payment.fetch(appt.razorpay_payment_id)
            amount = payment_info['amount']
            get_razorpay_client().payment.capture(appt.razorpay_payment_id, amount)
            appt.payment_status = "paid"
        except Exception as e:
            print(f"Razorpay Capture Error: {e}")
            # Even if capture fails, we might want to know why. 
            # If it's already captured, just proceed.
            if "already captured" in str(e).lower():
                appt.payment_status = "paid"
            else:
                return RedirectResponse(url="/dashboard?error=Payment+capture+failed", status_code=status.HTTP_302_FOUND)

    # 2. Update Status
    appt.status = "scheduled"
    await db.commit()

    # 3. Notify Student and Counsellor
    student = (await db.execute(select(models.User).where(models.User.id == appt.student_id))).scalars().first()
    if student:
        appt_time_str = appt.appointment_time.strftime('%b %d, %I:%M %p')
        # To Student
        background_tasks.add_task(
            send_email,
            student.email,
            "CareStance Session Confirmed! 🚀",
            get_booking_template(student.full_name, user.full_name, appt_time_str, appt.meeting_link, "student")
        )
        # To Counsellor
        background_tasks.add_task(
            send_email,
            user.email,
            "CareStance Session Confirmed! 🚀",
            get_booking_template(user.full_name, student.full_name, appt_time_str, appt.meeting_link, "counsellor")
        )
        # Add internal notification
        notif = models.Notification(
            user_id=student.id,
            type="booking_accepted",
            message=f"Counsellor {user.full_name} accepted your session for {appt_time_str}."
        )
        db.add(notif)
        await db.commit()

    return RedirectResponse(url="/dashboard?message=Appointment+accepted", status_code=status.HTTP_302_FOUND)


@app.post("/appointment/reject/{appt_id}")
async def reject_appointment(appt_id: int, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user or user.role != "counsellor":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    appt = (await db.execute(select(models.Appointment).where(models.Appointment.id == appt_id, models.Appointment.counsellor_id == user.id))).scalars().first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # 1. Release Payment (Refund if authorized)
    # Note: If only authorized, Razorpay doesn't have a direct "void" in the client lib sometimes, 
    # but not capturing it is the primary way. However, refunding an authorized payment voids it.
    if appt.payment_status == "authorized" and appt.razorpay_payment_id:
        try:
            # Refunding an authorized payment effectively releases the hold
            get_razorpay_client().payment.refund(appt.razorpay_payment_id, {})
            appt.payment_status = "refunded/released"
        except Exception as e:
            print(f"Razorpay Release Error: {e}")

    # 2. Update Status
    appt.status = "rejected"
    await db.commit()

    # 3. Notify Student
    student = (await db.execute(select(models.User).where(models.User.id == appt.student_id))).scalars().first()
    if student:
        appt_time_str = appt.appointment_time.strftime('%b %d, %I:%M %p')
        background_tasks.add_task(
            send_email,
            student.email,
            "Booking Notification ⚠️",
            f"Hi {student.full_name}, unfortunately, {user.full_name} is unable to take the session on {appt_time_str}. Your payment hold has been released."
        )
        notif = models.Notification(
            user_id=student.id,
            type="booking_rejected",
            message=f"Counsellor {user.full_name} rejected your session for {appt_time_str}. Hold released."
        )
        db.add(notif)
        await db.commit()

    return RedirectResponse(url="/dashboard?message=Appointment+rejected", status_code=status.HTTP_302_FOUND)

@app.post("/career/roadmap/delete/{path_id}")
async def delete_roadmap(path_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    
    await db.delete(path)
    await db.commit()
    return RedirectResponse(url="/career/roadmaps?message=Roadmap+deleted", status_code=status.HTTP_302_FOUND)


# --- Phase 3 Routes ---

from .data.questions_phase3 import CATEGORY_SCENARIOS_MAP

@app.get("/assessment/phase3", response_class=HTMLResponse)
async def assessment_phase3(request: Request, mode: str = "voice", db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)
        
    return templates.TemplateResponse(request=request, name="assessment_phase3_v2.html", context={"user": user, "result": result, "mode": mode})

@app.post("/assessment/phase3/submit")
async def assessment_phase3_submit(
    request: Request, 
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    try:
        form_data = await request.form()
    except Exception:
        # Client disconnected or bad request
        return RedirectResponse(url="/assessment/phase3", status_code=status.HTTP_302_FOUND)
    answers = {}
    
    for key, value in form_data.items():
        answers[key] = value

    # Save to DB
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        # Should likely have a phase 2 result first, but if not, create new?
        # For simplicity, we assume result exists. If not, redirect to start.
        return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)
    
    result.phase3_answers = answers
    result.phase3_result = "Phase 3 Completed" # Placeholder
    
    # Generate Phase 3 Analysis using Gemini
    category = result.phase_2_category
    # Inside assessment_phase3_submit route
    prompt_p3 = f"""
    You are an expert Career Mentor. Deep-dive into the scenario responses for a '{category}' profile.

    SCENARIO RESPONSES:
    {json.dumps(answers, indent=2)}

    TASK:
    Write a personal, narrative analysis (no bullet points).
    1. Acknowledge their specific choice in the most challenging scenario.
    2. Explain what this reveals about their 'Internal Compass' and leadership style.
    3. Use warm, sophisticated language that builds the student's confidence.

    STRICT RULE: No quotes, no markdown headers, max 4 sentences. 
    Start directly with: "It is fascinating to observe how you navigate..."
    """
    
    try:
         raw_text = await generate_content_with_fallback(prompt_p3)
         result.phase3_analysis = raw_text.replace('"', '').replace("'", "")
    except Exception as e:
         result.phase3_analysis = f"Analysis unavailable at this time. ({str(e)})"
        
    await db.commit()

    return RedirectResponse(url="/assessment/result", status_code=status.HTTP_302_FOUND)


# --- Phase 3 AI Chat Endpoint ---

class Phase3ChatRequest(BaseModel):
    message: str
    current_index: int = 0
    answers: dict = {}

COUNSELLOR_SYSTEM_PROMPT = """
You are an empathetic, professional career counsellor conducting a personality assessment.
Your role is to present scenario questions warmly and professionally.
- Keep your response concise (3-5 sentences max).
- When presenting a scenario, clearly state the two options (Option A and Option B) on separate lines.
- After the user selects an option, briefly acknowledge their choice with an encouraging sentence, then say you're moving to the next scenario.
- Do NOT make up new questions. Only work with the scenario data you are given.
"""

@app.post("/assessment/phase3/chat")
async def phase3_chat(request: Request, chat_req: Phase3ChatRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result or not result.phase_2_category:
        return JSONResponse({"error": "No phase 2 category found"})
    
    from fastapi.responses import JSONResponse
    category = result.phase_2_category
    question_list = CATEGORY_SCENARIOS_MAP.get(category, [])
    total = len(question_list)
    current_idx = chat_req.current_index

    # All done
    if current_idx >= total:
        return JSONResponse({
            "response": "Thank you for completing all the scenarios! Click **Finish Assessment** below to generate your personalised profile.",
            "current_index": current_idx,
            "answers": chat_req.answers,
            "done": True
        })

    current_scenario = question_list[current_idx]

    # Build the prompt
    scenario_text = f"""
Scenario {current_idx + 1} of {total}:
Title: {current_scenario['title']}
Story: {current_scenario['story']}
Option A: {current_scenario['options'][0]['text']}
Option B: {current_scenario['options'][1]['text']}
"""

    if chat_req.message and chat_req.message.strip():
        # User replied to previous question — acknowledge and show next
        next_idx = current_idx + 1
        if next_idx >= total:
            prompt = f"""{COUNSELLOR_SYSTEM_PROMPT}

The user just answered the previous scenario. Their reply was: "{chat_req.message}"
Acknowledge their answer warmly in 1-2 sentences, then let them know they have completed all scenarios and should click Finish."""
            new_idx = next_idx
            done = True
        else:
            next_scenario = question_list[next_idx]
            next_scenario_text = f"""
Scenario {next_idx + 1} of {total}:
Title: {next_scenario['title']}
Story: {next_scenario['story']}
Option A: {next_scenario['options'][0]['text']}
Option B: {next_scenario['options'][1]['text']}
"""
            prompt = f"""{COUNSELLOR_SYSTEM_PROMPT}

The user just answered the previous scenario. Their reply was: "{chat_req.message}"
Acknowledge their answer warmly in 1 sentence, then present the next scenario below.

{next_scenario_text}

Present the scenario story first, then clearly list Option A and Option B on separate lines."""
            new_idx = next_idx
            done = False
    else:
        # Initial load — present first scenario
        prompt = f"""{COUNSELLOR_SYSTEM_PROMPT}

Welcome the user warmly (1 sentence), then present this scenario:

{scenario_text}

Present the scenario story first, then clearly list Option A and Option B on separate lines."""
        new_idx = current_idx
        done = False

    # Call Groq (with Gemini fallback)
    try:
        gclient = get_groq_client()
        if gclient:
            try:
                completion = await gclient.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                ai_text = completion.choices[0].message.content
            except Exception as groq_err:
                print(f"Groq error: {groq_err}. Falling back to Gemini.")
                if GEMINI_API_KEY:
                    try:
                        model_ai = get_gemini_model("gemini-2.0-flash")
                        response = await model_ai.generate_content_async(prompt)
                        ai_text = response.text
                    except Exception:
                        model_ai = get_gemini_model("gemini-2.5-flash")
                        response = await model_ai.generate_content_async(prompt)
                        ai_text = response.text
                else:
                    raise groq_err
        elif GEMINI_API_KEY:
            try:
                model_ai = get_gemini_model("gemini-2.0-flash")
                response = await model_ai.generate_content_async(prompt)
                ai_text = response.text
            except Exception:
                model_ai = get_gemini_model("gemini-2.5-flash")
                response = await model_ai.generate_content_async(prompt)
                ai_text = response.text
        else:
            ai_text = f"[Demo Mode] {scenario_text}"
    except Exception as e:
        ai_text = f"I'm having a moment of reflection. ({str(e)}) Please try again."

    return JSONResponse({
        "response": ai_text,
        "current_index": new_idx,
        "answers": chat_req.answers,
        "done": done
    })


# --- Phase 3 v2: Voice-Only Deep-Dive Conversation (Groq-Powered) ---

from app.pipeline.prompts_phase3 import LIVE_CHAT_PROMPT

class Phase3V2ChatRequest(BaseModel):
    message: str = ""
    answers: list = []

@app.post("/assessment/phase3/chat_v2")
async def phase3_chat_v2(request: Request, chat_req: Phase3V2ChatRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from fastapi.responses import JSONResponse

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    
    # Determine if conversation should wrap up (after ~10 exchanges)
    user_msg_count = sum(1 for m in chat_req.answers if m.get("role") == "user")
    if chat_req.message.strip():
        user_msg_count += 1
        
    phase1 = result.raw_answers if result and result.raw_answers else {}
    
    student_context = {
        "student_name": phase1.get("name", "Student"),
        "age_group": result.student_type if result else "Unknown",
        "education_level": phase1.get("pursuing", "Unknown"),
        "current_course": phase1.get("pursuing", "Unknown"),
        "selected_interests": phase1.get("interests", []),
        "salary_priority": phase1.get("salary_priority", "Unknown"),
        "family_context": {
            "parent_occupation_category": f"{phase1.get('father_occupation', '')}, {phase1.get('mother_occupation', '')}",
            "family_income_category": phase1.get("family_income", "Unknown")
        },
        "phase_2_summary": {
            "strongest_work_style": result.phase_2_category if result else "Unknown",
            "learning_style": "Assessed via archetype",
            "problem_solving_style": "Assessed via archetype",
            "response_to_change": "Assessed via archetype",
            "leadership_and_team_style": "Assessed via archetype",
            "communication_style": "Assessed via archetype"
        },
        "conversation_turn": user_msg_count,
        "student_previous_answers_summary": "N/A"
    }

    all_interests = ", ".join(student_context["selected_interests"]) if student_context["selected_interests"] else "your fields of interest"
    parents_occupation = student_context["family_context"]["parent_occupation_category"] or "various fields"

    sys_prompt = LIVE_CHAT_PROMPT.format(
        context_json=json.dumps(student_context, indent=2),
        student_name=student_context["student_name"],
        all_interests=all_interests,
        parents_occupation=parents_occupation
    )

    # Build conversation history as messages for Groq
    messages = [
        {"role": "system", "content": sys_prompt}
    ]

    # Add conversation history
    if chat_req.answers:
        for msg in chat_req.answers:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})

    # Add current user message (if any)
    if chat_req.message.strip():
        messages.append({"role": "user", "content": chat_req.message})

    # Use Groq API directly
    try:
        gclient = get_groq_client()
        if gclient:
            completion = await gclient.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.8,
                max_tokens=300,
            )
            ai_text = completion.choices[0].message.content
        elif GEMINI_API_KEY:
            # Fallback to Gemini if Groq not available
            flat_prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
            ai_text = await generate_content_with_fallback(flat_prompt)
        else:
            ai_text = "Welcome! I am your CareStance Career Mentor. Tell me, what area or field excites you the most right now?"
    except Exception as e:
        print(f"Phase 3 Chat Error: {e}")
        ai_text = "I appreciate your patience. Could you tell me a bit more about that? I want to make sure I really understand your perspective."

    return JSONResponse({
        "response": ai_text,
        "done": False,
        "recommendation_ready": user_msg_count >= 10
    })


class Phase3FinalizeRequest(BaseModel):
    history: list = []

@app.post("/assessment/phase3/finalize")
async def phase3_finalize(request: Request, finalize_req: Phase3FinalizeRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from fastapi.responses import JSONResponse

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return JSONResponse({"redirect": "/assessment"})

    # Build conversation transcript
    transcript = ""
    for msg in finalize_req.history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        transcript += f"{role.upper()}: {content}\n"

    phase2_category = result.phase_2_category or "Unknown"

    phase2_category = result.phase_2_category or "Unknown"

    from app.pipeline.prompts_phase3 import FINALIZE_PROMPT
    phase1 = result.raw_answers if result and result.raw_answers else {}
    
    student_context = {
        "student_name": phase1.get("name", "Student"),
        "age_group": result.student_type if result else "Unknown",
        "education_level": phase1.get("pursuing", "Unknown"),
        "current_course": phase1.get("pursuing", "Unknown"),
        "selected_interests": phase1.get("interests", []),
        "salary_priority": phase1.get("salary_priority", "Unknown"),
        "family_context": {
            "parent_occupation_category": f"{phase1.get('father_occupation', '')}, {phase1.get('mother_occupation', '')}",
            "family_income_category": phase1.get("family_income", "Unknown")
        },
        "phase_2_summary": {
            "strongest_work_style": result.phase_2_category if result else "Unknown",
            "learning_style": "Assessed via archetype",
            "problem_solving_style": "Assessed via archetype",
            "response_to_change": "Assessed via archetype",
            "leadership_and_team_style": "Assessed via archetype",
            "communication_style": "Assessed via archetype"
        },
        "conversation_turn": "Finalized",
        "student_previous_answers_summary": "N/A"
    }

    import json
    analysis_prompt = FINALIZE_PROMPT.format(
        context_json=json.dumps(student_context, indent=2),
        transcript=transcript
    )

    try:
        raw_text = ""
        gclient = get_groq_client()
        if gclient:
            completion = await gclient.chat.completions.create(
                messages=[{"role": "user", "content": analysis_prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.4,
                max_tokens=2500,
                response_format={"type": "json_object"}
            )
            raw_text = completion.choices[0].message.content
        else:
            raw_text = await generate_content_with_fallback(analysis_prompt + "\nIMPORTANT: Return ONLY valid JSON without markdown formatting.")

        # Parse JSON
        data = json.loads(raw_text)
        
        # Safe Mapping to existing DB model so result.html doesn't break
        result.recommended_stream = "Personalized Career Matches"
        result.final_analysis = data.get("overall_summary", "Detailed conversation analysis complete.")
        result.phase3_analysis = f"Confidence: {data.get('confidence_level', 'High').title()} | {data.get('important_note', '')}"
        
        transformed_pros = []
        for rec in data.get("career_recommendations", []):
            transformed_pros.append({
                "title": rec.get("profession", "Unknown Profession"),
                "reason": f"Match Level: {rec.get('fit_level', '').replace('_', ' ').title()}. {rec.get('practical_next_step', '')}",
                "pros": rec.get("why_suitable", []) + rec.get("supporting_evidence_from_conversation", []),
                "cons": rec.get("likely_challenges", []) + rec.get("key_strengths_to_build", [])
            })
        
        result.stream_pros = transformed_pros
        result.stream_scores = {}
        result.phase3_result = json.dumps(data)

        result.final_answers = {"skipped": True, "flow": "simplified"}

    except Exception as e:
        print(f"Finalize Analysis Error: {e}")
        # Soft fallback
        result.phase3_analysis = "We've captured your insights and mapped them to your potential."
        
    await db.commit()

    return JSONResponse({"redirect": "/assessment/result"})


# --- Simulation Phase Routes ---

@app.get("/assessment/simulation/pay/{category}/{career_title}", response_class=HTMLResponse)
async def simulation_pay_with_category(category: str, career_title: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await simulation_pay(career_title, request, db)

@app.get("/assessment/simulation/pay/{career_title}", response_class=HTMLResponse)
async def simulation_pay(career_title: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)


    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(request=request, name="simulation_payment.html", context={
        "user": user,
        "career_title": career_title,
        "RAZORPAY_KEY_ID": RAZORPAY_KEY_ID
    })

@app.post("/assessment/simulation/create-order")
async def simulation_create_order(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
        
    req_data = await request.json()
    package = req_data.get("package", "single") # "single" or "bundle"
    amount_in_inr = 35 if package == "bundle" else 15
    
    data = {
        "amount": amount_in_inr * 100, # paise
        "currency": "INR",
        "receipt": f"receipt_sim_{uuid.uuid4().hex[:10]}",
        "payment_capture": 1
    }
    
    try:
        order = get_razorpay_client().order.create(data=data)
        return order
    except Exception as e:
        print(f"Razorpay Simulation Order Create Error: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment order")

@app.post("/assessment/simulation/verify-payment")
async def simulation_verify_payment(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
        
    data = await request.json()
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")
    package = data.get("package", "single")
    
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    
    try:
        get_razorpay_client().utility.verify_payment_signature(params_dict)
    except Exception as e:
        print(f"Simulation Payment Verification Failed: {e}")
        raise HTTPException(status_code=400, detail="Signature verification failed")
        
    credits_to_add = 3 if package == "bundle" else 1
    amount_paid = 35.0 if package == "bundle" else 15.0
        
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if result:
        result.simulation_paid = True
        result.simulation_credits = (result.simulation_credits or 0) + credits_to_add
        
    db_user = (await db.execute(select(models.User).where(models.User.id == user.id))).scalars().first()
    if db_user:
        db_user.simulation_paid = True
        db_user.simulation_credits = (db_user.simulation_credits or 0) + credits_to_add
        
    # Add payment record
    career_title = data.get("career_title", (result.simulation_career if result else None) or "General")
    sim_pay = models.SimulationPayment(
        user_id=user.id,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        amount=amount_paid,
        career=career_title
    )
    db.add(sim_pay)
    await db.commit()
        
    return {"status": "ok"}

@app.get("/assessment/simulation/start/{category}/{career_title}", response_class=HTMLResponse)
async def simulation_start_with_category(category: str, career_title: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await simulation_start(career_title, request, db)

@app.get("/assessment/simulation/start/{career_title}", response_class=HTMLResponse)
async def simulation_start(career_title: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)
    
    db_user = (await db.execute(select(models.User).where(models.User.id == user.id))).scalars().first()
    sims_completed = max(result.simulations_completed or 0, db_user.simulations_completed or 0 if db_user else 0)
    sim_credits = max(result.simulation_credits or 0, db_user.simulation_credits or 0 if db_user else 0)

    if sims_completed >= 1 and sim_credits <= 0:
        return RedirectResponse(url=f"/assessment/simulation/pay/{career_title}", status_code=status.HTTP_302_FOUND)
    
    # Generate questions based on class
    if result.selected_class == '10th':
        questions = await simulation_service.generate_academic_simulation_questions(career_title)
    else:
        questions = await simulation_service.generate_simulation_questions(career_title)

    if not questions:
        return RedirectResponse(url="/assessment/result?error=failed_to_generate_simulation", status_code=status.HTTP_302_FOUND)
    
    # Appwrite Update
    update_assessment_simulation(user.id, career=career_title, questions=questions, answers=[], evaluation=None)
    
    # SQL Fallback
    result.simulation_career = career_title
    result.simulation_questions = questions
    result.simulation_answers = [] # Reset answers
    result.simulation_evaluation = None # Reset evaluation
    
    if sims_completed >= 1:
        if result.simulation_credits > 0:
            result.simulation_credits -= 1
        if db_user and db_user.simulation_credits > 0:
            db_user.simulation_credits -= 1

    if result.simulation_paid:
        result.simulation_paid = False
    if db_user and db_user.simulation_paid:
        db_user.simulation_paid = False
        
    await db.commit()
    
    return RedirectResponse(url="/assessment/simulation/question/0", status_code=status.HTTP_302_FOUND)

@app.get("/assessment/simulation/question/{index}", response_class=HTMLResponse)
async def simulation_question(index: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result or not result.simulation_questions:
        return RedirectResponse(url="/assessment/result", status_code=status.HTTP_302_FOUND)
    
    questions = result.simulation_questions
    if index < 0 or index >= len(questions):
        return RedirectResponse(url="/assessment/simulation/result", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(request=request, name="assessment_simulation.html", context={
        "user": user,
        "career_title": result.simulation_career,
        "question": questions[index],
        "index": index,
        "total": len(questions),
        "progress": int(((index + 1) / len(questions)) * 100)
    })

@app.post("/assessment/simulation/answer")
async def simulation_answer(
    request: Request, 
    index: int = Form(...), 
    answer: str = Form(...), 
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        return RedirectResponse(url="/assessment", status_code=status.HTTP_302_FOUND)
    
    # Update answers list
    current_answers = list(result.simulation_answers) if result.simulation_answers else []
    # Ensure list is long enough
    while len(current_answers) <= index:
        current_answers.append("")
    current_answers[index] = answer
    
    # Appwrite Update
    update_assessment_simulation(user.id, answers=current_answers)
    
    # SQL Fallback
    result.simulation_answers = current_answers
    await db.commit()
    
    next_index = index + 1
    if next_index < len(result.simulation_questions):
        return RedirectResponse(url=f"/assessment/simulation/question/{next_index}", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(url="/assessment/simulation/result", status_code=status.HTTP_302_FOUND)

@app.get("/assessment/simulation/result", response_class=HTMLResponse)
async def simulation_result(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result or not result.simulation_answers:
        return RedirectResponse(url="/assessment/result", status_code=status.HTTP_302_FOUND)
    
    # Trigger evaluation if not already done
    if not result.simulation_evaluation:
        if result.selected_class == '10th':
            evaluation = await simulation_service.evaluate_academic_simulation(
                result.simulation_career,
                result.simulation_questions,
                result.simulation_answers
            )
        else:
            evaluation = await simulation_service.evaluate_simulation(
                result.simulation_career,
                result.simulation_questions,
                result.simulation_answers
            )
        
        # Appwrite Update
        update_assessment_simulation(user.id, evaluation=evaluation)
        
        # SQL Fallback
        result.simulation_evaluation = evaluation
        result.simulations_completed += 1
        db_user = (await db.execute(select(models.User).where(models.User.id == user.id))).scalars().first()
        if db_user:
            db_user.simulations_completed += 1
        await db.commit()
    
    return templates.TemplateResponse(request=request, name="simulation_result.html", context={
        "user": user,
        "career": result.simulation_career,
        "evaluation": result.simulation_evaluation
    })


# --- Public Shareable Simulation Result ---
@app.get("/share/simulation/{result_id}", response_class=HTMLResponse)
async def share_simulation_result(result_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.id == result_id))).scalars().first()
    if not result or not result.simulation_evaluation:
        raise HTTPException(status_code=404, detail="Simulation result not found")
    
    owner = (await db.execute(select(models.User).where(models.User.id == result.user_id))).scalars().first()
    return templates.TemplateResponse(request=request, name="simulation_result.html", context={
        "user": None,
        "owner": owner,
        "career": result.simulation_career,
        "evaluation": result.simulation_evaluation,
        "is_public_share": True
    })


# --- Phase 4 Routes (Final Stream Assessment) ---

from .data.questions_final import all_questions, section_a_questions, section_b_questions, section_c_questions, section_d_questions
from .data.questions_12th import questions_12th
from .data.questions_above_12th import questions_above_12th

@app.get("/assessment/final", response_class=HTMLResponse)
async def assessment_final(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Get user class selection
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    selected_class = result.selected_class if result else "10th" # Default to 10th if not found

    context = {
        "request": request, 
        "user": user,
    }

    if selected_class == "12th":
        context["mode"] = "12th"
        context["questions"] = questions_12th
    elif selected_class == "Above 12th": # Ensure this matches the exact string saved in Phase 1
        context["mode"] = "above"
        context["questions"] = questions_above_12th
    else:
        # Default to Class 10th (Existing Logic)
        context["mode"] = "10th"
        context["sections"] = all_questions

    return templates.TemplateResponse(request=request, name="assessment_final.html", context=context)

@app.post("/assessment/final/submit")
async def assessment_final_submit(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    form_data = await request.form()
    answers = {}
    mode = form_data.get("mode", "10th") # Default to 10th if missing
    print(f"DEBUG: Submitting Final Assessment. Mode: {mode}")

    for key, value in form_data.items():
        if key != "mode":
            answers[key] = value
        
    # fetch result object
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    
    # --- Logic Branching based on Mode ---
    
    if mode == "10th":
        # ... EXISTING LOGIC FOR CLASS 10 (PCM/PCB/COMM/ARTS/VOC) ...
        # (Keeping the original rule-based scoring for Class 10 reliability)
        scores = { "PCM": 0, "PCB": 0, "COMM": 0, "ARTS": 0, "VOC": 0 }
        
        def add_points(streams, points=1):
            for s in streams:
                if s in scores: scores[s] += points

        # 1. Section A
        for q in section_a_questions:
            if answers.get(q["id"]) == q["correct_value"]:
                add_points(q["mapped_streams"], points=2)

        # 2. Preference Sections
        preference_questions = section_b_questions + section_c_questions + section_d_questions
        for q in preference_questions:
            user_ans = answers.get(q["id"])
            if not user_ans: continue
            selected_opt = next((opt for opt in q["options"] if opt["value"] == user_ans), None)
            if selected_opt and "stream" in selected_opt:
                 add_points([selected_opt["stream"]], points=1)
            else:
                if user_ans == "a":
                    txt = q["question"] + " " + (selected_opt["text"] if selected_opt else "")
                    if any(x in txt.lower() for x in ["plant", "health", "bio", "nutri", "species", "cures"]):
                         add_points(["PCB"], points=1)
                    else:
                         add_points(["PCM"], points=1)
                elif user_ans == "b": add_points(["COMM"], points=1)
                elif user_ans == "c": add_points(["ARTS"], points=1)
                elif user_ans == "d": add_points(["VOC"], points=1)

        # 3. Phase 2 Influence
        if result and result.phase_2_category:
            cat = result.phase_2_category
            if cat == "Focused Specialist": add_points(["PCM", "PCB"], points=3)
            elif cat == "Quiet Explorer": add_points(["PCB", "ARTS"], points=3)
            elif cat == "Visionary Leader": add_points(["COMM", "ARTS"], points=3)
            elif cat == "Strategic Builder": add_points(["PCM", "COMM"], points=3)
            elif cat == "Adaptive Explorer": add_points(["ARTS", "VOC"], points=3)
            elif cat == "Dynamic Generalist": add_points(["COMM", "VOC"], points=3)

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        winner_code = sorted_scores[0][0]
        code_map = { "PCM": "Science (PCM)", "PCB": "Science (PCB)", "COMM": "Commerce", "ARTS": "Arts & Humanities", "VOC": "Vocational Studies" }
        winner_name = code_map.get(winner_code, winner_code)
        
        # Save Score & Result
        if result:
            result.stream_scores = scores
            result.recommended_stream = winner_name

    else:
        # --- Logic for Class 12th & Above (No fixed scoring, pure AI Analysis) ---
        # We don't have a specific "stream" to recommend in the same way, but we will use the field for the primary recommendation
        scores = {} # Not used
        winner_name = "See Analysis" # Placeholder
        if result:
            result.stream_scores = {}
            result.recommended_stream = "AI Analyzing..." # Temporary

    # --- Common Save ---
    if result:
        result.final_answers = answers
        
        # --- AI Analysis (Gemini) ---
        if GEMINI_API_KEY:
            try:
                # Prepare Prompt based on Mode
                readable_answers = []
                
                if mode == "10th":
                    def get_question_text(q_id):
                        for section in all_questions.values():
                            for q in section["questions"]:
                                if q["id"] == q_id: 
                                    return q["question"], q.get("options")
                        return None, None

                    for q_id, ans_value in answers.items():
                        q_text, options = get_question_text(q_id)
                        if q_text:
                            if options:
                                selected_option = next((opt for opt in options if opt["value"] == ans_value), None)
                                ans_text = selected_option["text"] if selected_option else f"Value: {ans_value}"
                            else:
                                ans_text = ans_value # Direct text for open questions
                            readable_answers.append(f"Question: {q_text}\nSelected Answer: {ans_text}")
                
                elif mode == "12th":
                     # Use questions_12th data
                     q_map = {q["id"]: q for q in questions_12th}
                     for q_id, ans_text in answers.items():
                         if q_id in q_map:
                             q_title = q_map[q_id].get('title') or q_map[q_id].get('question')
                             readable_answers.append(f"Scenario: {q_title}\nInsight: {q_map[q_id]['insight']}\nUser Response: {ans_text}")

                elif mode == "above":
                     # Use questions_above_12th data
                     q_map = {q["id"]: q for q in questions_above_12th}
                     for q_id, ans_text in answers.items():
                         if q_id in q_map:
                             q_title = q_map[q_id].get('title') or q_map[q_id].get('question')
                             readable_answers.append(f"Question: {q_title}\nContext: {q_map[q_id]['insight']}\nUser Response: {ans_text}")

                answers_summary = "\n\n".join(readable_answers)
                phase2_cat = result.phase_2_category or "Unknown"
                
                # Dynamic Prompt Construction based on Class
                if mode == "10th":
                    task_instruction = f"""
                    1. The student's calculated best fit based on answers is "{winner_name}". Validate and Analyze this choice.
                    2. Provide a "Final Analysis" (approx 150 words) explaining WHY {winner_name} is the best fit based on their answers.
                    3. Provide 3 "Pros" (Why {winner_name} is good for the student).
                    4. Provide 3 "Cons" (Challenges to consider).
                    """
                    output_format = """
                    {
                      "recommended_stream": "Exact Stream Name",
                      "final_analysis": "Detailed explanation...",
                      "stream_pros": ["Pro 1", "Pro 2", "Pro 3"],
                      "stream_cons": ["Con 1", "Con 2", "Con 3"]
                    }
                    """
                elif mode == "12th":
                    task_instruction = """
                    1. Identify the Top 3 Career Goals / University Majors best suited for this student based on their scenarios.
                    2. For EACH goal, provide a specific "Reason" why they should go for that.
                    3. For EACH goal, provide 2 "Pros" (Advantages) and 2 "Cons" (Challenges).
                    4. Provide a "Final Analysis" (approx 100 words) summarizing their potential.
                    """
                    output_format = """
                    {
                      "recommended_stream": "Primary Field (e.g. Technology, Healthcare, Creative Arts)",
                      "final_analysis": "Summary...",
                      "goal_options": [
                        {
                            "title": "Option 1 Title", 
                            "reason": "Why they should choose this...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        },
                        {
                            "title": "Option 2 Title", 
                            "reason": "Why they should choose this...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        },
                        {
                            "title": "Option 3 Title", 
                            "reason": "Why they should choose this...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        }
                      ]
                    }
                    """
                else: # Above 12th
                    task_instruction = """
                    1. Identify the Top 3 Professional Roles / Niche Career Paths best suited for this student.
                    2. For EACH goal, provide a specific "Reason" why they should pursue it.
                    3. For EACH goal, provide 2 "Pros" (Advantages) and 2 "Cons" (Challenges).
                    4. Provide a "Final Analysis" (approx 100 words) on their professional outlook.
                    """
                    output_format = """
                    {
                      "recommended_stream": "Primary Field / Industry",
                      "final_analysis": "Summary...",
                      "goal_options": [
                        {
                            "title": "Role 1 Title", 
                            "reason": "Why this fits...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        },
                        {
                            "title": "Role 2 Title", 
                            "reason": "Why this fits...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        },
                        {
                            "title": "Role 3 Title", 
                            "reason": "Why this fits...",
                            "pros": ["Pro 1", "Pro 2"],
                            "cons": ["Con 1", "Con 2"]
                        }
                      ]
                    }
                    """

                prompt = f"""
                You are a fascinating and expert career counselor mentor. 
                Analyze this profile for a {mode} grade student with deep curiosity and professional empathy.

                Profile:
                - Archetype: {phase2_cat}
                - Insights Table:
                {answers_summary}

                Task:
                {task_instruction}
                
                CRITICAL ADDITION:
                In addition to the top 3 recommendations requested above, YOU MUST provide a 4th recommendation directly related to the student's hobbies and extracurricular interests (e.g. {answers.get('PI1_Hobbies', 'N/A')}, {answers.get('PI2_Extracurricular', 'N/A')}).
                
                Even if it's outside the standard academic path, suggest how their hobbies could lead to a professional career.
                
                The 4th recommendation should be returned in the same format as the others, but clearly labeled as "Hobby-based Recommendation" in your reasoning.

                You must speak with authority yet warmth. Output MUST be raw JSON only matching this structure. 
                {output_format}
                """
                
                # Generate Content with Fallback
                text = await generate_content_with_fallback(prompt)
                print(f"DEBUG: AI Raw Text: {text}")
                ai_data = json.loads(text)
                
                if mode != "10th" and "recommended_stream" in ai_data: 
                     result.recommended_stream = ai_data["recommended_stream"]
                if "final_analysis" in ai_data: result.final_analysis = ai_data["final_analysis"]
                
                # Handling Data Mapping
                if mode == "10th":
                    if "stream_pros" in ai_data: result.stream_pros = ai_data["stream_pros"]
                    if "stream_cons" in ai_data: result.stream_cons = ai_data["stream_cons"]
                    # Add hobby recommendation to analysis text
                    if "goal_options" in ai_data and len(ai_data["goal_options"]) > 0:
                        hobby_rec = ai_data["goal_options"][-1]
                        if isinstance(hobby_rec, dict):
                            title = hobby_rec.get('title', 'Alternative Path')
                            reason = hobby_rec.get('reason', '')
                            # Ensure final_analysis is a string before appending
                            if not result.final_analysis:
                                result.final_analysis = ""
                            result.final_analysis += f"\n\n**Special Interest Recommendation:** Based on your hobbies, you might also consider a career as a {title}. {reason}"
                else:
                    # Map 'goal_options' to 'stream_pros' for storage
                    if "goal_options" in ai_data: result.stream_pros = ai_data["goal_options"]
                    result.stream_cons = [] # Not used for 12th/Above
                    
            except Exception as e:
                print(f"AI Analysis Failed: {e}")
                result.final_analysis = f"AI Analysis Unavailable. (Error: {str(e)})"
        else:
             result.final_analysis = "AI Analysis Unavailable (API Key missing)."

        await db.commit()

    return RedirectResponse(url="/assessment/result", status_code=status.HTTP_302_FOUND)


# --- Final Phase AI Chat Endpoint ---

class FinalChatRequest(BaseModel):
    message: str
    current_index: int = 0
    answers: dict = {}
    mode: str = "10th"

FINAL_COUNSELLOR_PROMPT = """
You are a warm and insightful AI career counsellor conducting a final career assessment.
Your tone is encouraging, curious, and professional.
- Keep responses concise (3-5 sentences).
- For Multiple Choice questions (10th mode), present the question then list ALL options clearly (A, B, C, D or as given).
- For open-ended scenarios (12th / above mode), present the scenario warmly, then invite the student to share their thoughts.
- After the student replies, give a brief, encouraging acknowledgement (1 sentence) before presenting the next question.
- Never make up questions. Only use the question data provided to you.
"""

@app.post("/assessment/final/chat")
async def final_chat(request: Request, chat_req: FinalChatRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from fastapi.responses import JSONResponse
    mode = chat_req.mode
    current_idx = chat_req.current_index

    # Build flat question list based on mode
    if mode == "10th":
        flat_questions = []
        for section_id, section_data in all_questions.items():
            for q in section_data["questions"]:
                q_dict = {
                    "id": q["id"],
                    "title": q["question"],
                    "section": section_data["title"]
                }
                if q.get("type") == "open":
                    q_dict["type"] = "open"
                else:
                    q_dict["type"] = "mcq"
                    q_dict["options"] = [{"value": o["value"], "text": o["text"]} for o in q["options"]]
                flat_questions.append(q_dict)
    elif mode == "12th":
        flat_questions = [
            {"id": q["id"], "title": q.get("title") or q.get("question"), "text": q.get("text"), "insight": q["insight"], "type": "open"}
            for q in questions_12th
        ]
    else:  # above
        flat_questions = [
            {"id": q["id"], "title": q.get("title") or q.get("question"), "text": q.get("text"), "insight": q["insight"], "type": "open"}
            for q in questions_above_12th
        ]

    total = len(flat_questions)

    # All done
    if current_idx >= total:
        return JSONResponse({
            "response": "Wonderful! You've answered all the questions. Click **Get My Career Path** to generate your personalised AI career insights! 🎯",
            "current_index": current_idx,
            "answers": chat_req.answers,
            "done": True
        })

    # Format current question for the prompt
    q = flat_questions[current_idx]
    if q["type"] == "mcq":
        options_text = "\n".join([f"  Option {o['value'].upper()}: {o['text']}" for o in q["options"]])
        current_q_text = f"""Question {current_idx + 1} of {total} [{q['section']}]:
{q['title']}
{options_text}"""
    else:
        current_q_text = f"""Question {current_idx + 1} of {total}:
Title: {q['title']}
Scenario: {q['text']}
(Focus: {q['insight']})"""

    if chat_req.message and chat_req.message.strip():
        # User replied — move to next
        next_idx = current_idx + 1
        if next_idx >= total:
            prompt = f"""{FINAL_COUNSELLOR_PROMPT}

The student just answered a question. Their response: "{chat_req.message}"
Give a warm 1-sentence acknowledgement, then tell them they've completed all questions and should click the button to get their results."""
            new_idx = next_idx
            done = True
        else:
            next_q = flat_questions[next_idx]
            if next_q["type"] == "mcq":
                next_opts = "\n".join([f"  Option {o['value'].upper()}: {o['text']}" for o in next_q["options"]])
                next_q_text = f"""Question {next_idx + 1} of {total} [{next_q['section']}]:
{next_q['title']}
{next_opts}"""
            else:
                next_q_text = f"""Question {next_idx + 1} of {total}:
Title: {next_q['title']}
Scenario: {next_q['text']}
(Focus: {next_q['insight']})"""
            prompt = f"""{FINAL_COUNSELLOR_PROMPT}

The student just answered the previous question. Their response: "{chat_req.message}"
Acknowledge in 1 warm sentence, then present the next question:

{next_q_text}"""
            new_idx = next_idx
            done = False
    else:
        # First load — present first question
        prompt = f"""{FINAL_COUNSELLOR_PROMPT}

Welcome the student warmly (1 sentence), then present this first question:

{current_q_text}"""
        new_idx = current_idx
        done = False

    # Call Groq with Gemini fallback
    try:
        gclient = get_groq_client()
        if gclient:
            try:
                completion = await gclient.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                ai_text = completion.choices[0].message.content
            except Exception as groq_err:
                print(f"Groq error: {groq_err}. Falling back to Gemini.")
                if GEMINI_API_KEY:
                    try:
                        model_ai = get_gemini_model("gemini-2.0-flash")
                        response = await model_ai.generate_content_async(prompt)
                        ai_text = response.text
                    except Exception:
                        model_ai = get_gemini_model("gemini-2.5-flash")
                        response = await model_ai.generate_content_async(prompt)
                        ai_text = response.text
                else:
                    raise groq_err
        elif GEMINI_API_KEY:
            try:
                model_ai = get_gemini_model("gemini-2.0-flash")
                response = await model_ai.generate_content_async(prompt)
                ai_text = response.text
            except Exception:
                model_ai = get_gemini_model("gemini-2.5-flash")
                response = await model_ai.generate_content_async(prompt)
                ai_text = response.text
        else:
            ai_text = f"[Demo Mode] {current_q_text}"
    except Exception as e:
        ai_text = f"I seem to be in deep thought right now. ({str(e)}) Please try again."

    return JSONResponse({
        "response": ai_text,
        "current_index": new_idx,
        "answers": chat_req.answers,
        "done": done
    })


# --- Bark TTS Route ---

import httpx

@app.get("/api/tts")
async def generate_tts(text: str):
    """
    Generates high-quality audio using stable models (MMS) or expressive models (Bark).
    """
    HF_TOKEN = os.getenv("HF_TOKEN")
    
    # Switch to facebook/mms-tts-eng for a MUCH more stable, professional, and clear voice.
    # Bark (suno/bark) is artistic but often "cracky" or "glitchy" on the serverless API.
    API_URL = "https://api-inference.huggingface.co/models/facebook/mms-tts-eng"
    
    # Optional: If you REALLY want Bark, we can add a prompt to it, 
    # but MMS is recommended for clear educational/assessment questions.
    # API_URL = "https://api-inference.huggingface.co/models/suno/bark-small"

    if not HF_TOKEN:
        return {"error": "HF_TOKEN missing in .env", "fallback": True}

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        try:
            # For Bark, we'd want to prepend a voice preset like "[v2/en_speaker_6]"
            # But for MMS, we just send the text.
            payload = {"inputs": text}
            
            response = await client.post(API_URL, headers=headers, json=payload, timeout=30.0)
            
            if response.status_code == 200:
                return Response(content=response.content, media_type="audio/wav")
            elif response.status_code == 503:
                return JSONResponse({"error": "Model loading..."}, status_code=503)
            else:
                return JSONResponse({"error": f"HF Error: {response.text}"}, status_code=500)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)


# --- Chatbot Routes ---

class ChatRequest(BaseModel):
    message: str

class ResolveVoiceRequest(BaseModel):
    transcript: str
    options: list

@app.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Fetch History
    history = (await db.execute(select(models.ChatMessage).where(models.ChatMessage.user_id == user.id).order_by(models.ChatMessage.timestamp))).scalars().all()
    
    try:
        template = templates.get_template("chatbot.html")
        content = template.render({"request": request, "user": user, "history": history})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/assessment/resolve-voice")
async def resolve_voice(req: ResolveVoiceRequest):
    """
    Uses AI to match a voice transcript to one of the provided multiple-choice options.
    """
    prompt = f"""
    The student spoke this answer for a career assessment question: "{req.transcript}"
    
    Which of these options best matches what they said?
    Options:
    {json.dumps(req.options, indent=2)}
    
    Output ONLY valid JSON with the field "best_match" containing the "value" of the matching option.
    If no good match exists, return the most likely one based on interest.
    """
    
    try:
        clean_text = await generate_content_with_fallback(prompt)
        result = json.loads(clean_text)
        return result
    except Exception as e:
        print(f"Voice Resolution Error: {e}")
        # Default to the first option if AI fails
        return {"best_match": req.options[0]["value"] if req.options else "A"}

# --- Chatbot Routes ---

@app.post("/chatbot/message")
async def chatbot_message(request: Request, chat_req: ChatRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if user.is_suspended:
        return {"error": "Your account has been suspended for violating our content policies."}

    user_message = chat_req.message
    
    # Content Moderation Check
    is_flagged, reason = await check_content_moderation(user_message)
    if is_flagged:
        flag = models.ModerationFlag(user_id=user.id, content=user_message, chat_type="ai", status="pending_review")
        db.add(flag)
        await db.commit()
        return {"error": "Your message was flagged as inappropriate. Repeated violations will lead to account suspension."}

    # Save User Message
    user_msg_db = models.ChatMessage(user_id=user.id, sender="user", content=user_message)
    db.add(user_msg_db)
    await db.commit()
    
    # 1. Build Context from DB
    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    
    context_str = f"User Name: {user.full_name}\n"
    if result:
        if result.selected_class:
            context_str += f"Class/Grade: {result.selected_class}\n"
        if result.phase_2_category:
            context_str += f"Personality Archetype: {result.phase_2_category}\n"
        if result.recommended_stream:
            context_str += f"Recommended Path: {result.recommended_stream}\n"
        
        # Add slight detail if available
        if result.phase3_analysis:
             context_str += f"Work Style Analysis: {result.phase3_analysis[:200]}...\n"

    # Fetch recent history for context
    recent_history = (await db.execute(select(models.ChatMessage).where(models.ChatMessage.user_id == user.id).order_by(models.ChatMessage.timestamp.desc()).limit(10))).scalars().all()
    recent_history.reverse() # Oldest first
    history_str = "\n".join([f"{msg.sender.upper()}: {msg.content}" for msg in recent_history])

    # 2. Construct System Prompt
    prompt = f"""
You are the 'CareStance Mentor'. You are professional, deeply empathetic, and highly knowledgeable about global career trends.

STUDENT PROFILE:
- Name: {user.full_name}
- Grade Level: {result.selected_class if result else 'Not Selected'}
- Archetype: {result.phase_2_category if result else 'Analyzing...'}
- Calculated Recommendation: {result.recommended_stream if result else 'In progress'}

GUIDELINES:
1. PERSONALIZATION: If the student asks 'What should I do?', refer to their Archetype ({result.phase_2_category}) specifically.
2. TONE: Be a mentor, not an encyclopedia. Use phrases like "Looking at your preference for {result.personality if result else 'collaboration'}..."
3. STRUCTURE: Use bold text for key career roles and bullet points for steps.
4. SCOPE: Focus 100% on careers, education, and professional growth.

LATEST STUDENT MESSAGE: "{user_message}"
CONVERSATION HISTORY: {history_str}

Response (Concise, Markdown formatted):
"""
    
    # 3. Stream AI Response with Fallback
    user_id = user.id
    async def generate():
        full_response_text = ""
        # Create a new local session for the generator because the route session 
        # closes after the response object is returned but before streaming finishes.
        from .database import AsyncSessionLocal
        async with AsyncSessionLocal() as local_db:
            try:
                # TRY GROQ FIRST
                gclient = get_groq_client()
                if gclient:
                    try:
                        print(f"AI Chat for User {user_id}: Trying Groq...")
                        stream = await gclient.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile",
                            stream=True,
                        )
                        async for chunk in stream:
                            if chunk.choices[0].delta.content:
                                text_chunk = chunk.choices[0].delta.content
                                full_response_text += text_chunk
                                yield text_chunk
                    except Exception as groq_e:
                        print(f"Chatbot Groq Error: {groq_e}. Trying Gemini fallback.")
                        if GEMINI_API_KEY:
                            try:
                                model = get_gemini_model("gemini-2.5-flash")
                                response = await model.generate_content_async(prompt, stream=True)
                                async for chunk in response:
                                    if chunk.text:
                                        text_chunk = chunk.text
                                        full_response_text += text_chunk
                                        yield text_chunk
                            except Exception as gemini_e:
                                print(f"Chatbot Gemini Error: {gemini_e}")
                                yield f"I'm sorry, both AI services are currently unavailable. (Groq: {str(groq_e)}, Gemini: {str(gemini_e)})"
                        else:
                            yield f"AI Service error: {str(groq_e)}"
                elif GEMINI_API_KEY:
                    try:
                        print(f"AI Chat for User {user_id}: Trying Gemini...")
                        model = get_gemini_model("gemini-2.5-flash")
                        response = await model.generate_content_async(prompt, stream=True)
                        async for chunk in response:
                            if chunk.text:
                                text_chunk = chunk.text
                                full_response_text += text_chunk
                                yield text_chunk
                    except Exception as gemini_e:
                        yield f"AI Service error: {str(gemini_e)}"
                else:
                     # Demo Mode Simulation
                     fake_response = "I'm in demo mode (No API Key). Based on your profile, I'd suggest exploring based on your interests! (Please set GEMINI_API_KEY or GROQ_API_KEY to get real AI responses)"
                     for word in fake_response.split():
                         text_chunk = word + " "
                         full_response_text += text_chunk
                         yield text_chunk
                         import asyncio
                         await asyncio.sleep(0.05) 
                
                # Save AI Message using local_db
                if full_response_text:
                    ai_msg_db = models.ChatMessage(user_id=user_id, sender="ai", content=full_response_text)
                    local_db.add(ai_msg_db)
                    await local_db.commit()
                    print(f"AI Chat for User {user_id}: Message saved.")
    
            except Exception as e:
                print(f"Chat Error in generator: {e}")
                error_msg = f"I'm having a little trouble thinking right now. (Error: {str(e)})"
                yield error_msg
                try:
                    ai_msg_db = models.ChatMessage(user_id=user_id, sender="ai", content=error_msg)
                    local_db.add(ai_msg_db)
                    await local_db.commit()
                except Exception as db_e:
                    print(f"Failed to save error message to DB: {db_e}")
    
    return StreamingResponse(generate(), media_type="text/plain")


# --- Feedback Routes ---

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    try:
        template = templates.get_template("feedback.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/feedback")
async def submit_feedback(
    request: Request,
    content: str = Form(...),
    rating: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    new_feedback = models.Feedback(
        user_id=user.id,
        content=content,
        rating=rating
    )
    db.add(new_feedback)
    await db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

# --- Ticket System Routes ---

@app.get("/ticket", response_class=HTMLResponse)
async def ticket_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    tickets = (await db.execute(select(models.Ticket).where(models.Ticket.user_id == user.id).order_by(models.Ticket.timestamp.desc()))).scalars().all()
    return templates.TemplateResponse(request=request, name="ticket.html", context={"user": user, "tickets": tickets})

@app.post("/ticket/submit")
async def submit_ticket(
    request: Request,
    subject: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    new_ticket = models.Ticket(
        user_id=user.id,
        subject=subject,
        description=description
    )
    db.add(new_ticket)
    await db.commit()
    
    if user.is_suspended:
        return RedirectResponse(url="/suspended?ticket_submitted=true", status_code=status.HTTP_302_FOUND)
        
    return RedirectResponse(url="/ticket", status_code=status.HTTP_302_FOUND)


# --- Career Path Generation ---

class CareerPathRequest(BaseModel):
    career_title: str

@app.post("/assessment/generate_path")
async def generate_career_path(request: Request, path_req: CareerPathRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Assessment results not found")

    archetype = result.phase_2_category or "Explorer"
    personality = result.personality or "Ambivert"
    current_class = result.selected_class or "10th"
    phase3_insight = result.phase3_analysis or ""
    final_insight = result.final_analysis or ""

    prompt = f"""
You are CareStance's Elite Career Architect, Industry Mentor, and Student Success Strategist.

Student Profile:
- Current Stage: {current_class}
- Archetype: {archetype}
- Personality: {personality}
- Goal Career: {path_req.career_title}
- Deep Analysis Context: {phase3_insight[:600]}
- Recommendation Engine Notes: {final_insight[:600]}

TASK:

Create a highly personalized "Zero-to-Hero Career Journey" for this student.

IMPORTANT:

DO NOT generate a fixed number of roadmap steps.

First analyze:

1. Complexity of {path_req.career_title}
2. Required education level
3. Skill depth required
4. Certification requirements
5. Industry expectations
6. Portfolio requirements
7. Experience requirements
8. Time required to become job-ready

Based on this analysis dynamically determine the roadmap size.

Roadmap Guidelines:

- Simple Careers → 6-8 milestones
- Moderate Careers → 8-10 milestones
- Advanced Careers → 10-14 milestones
- Highly Specialized Careers → 14-20 milestones

Examples:

Data Analyst → 8 Milestones
Software Engineer → 10 Milestones
AI/ML Engineer → 12 Milestones
Cybersecurity Engineer → 12 Milestones
Doctor → 18 Milestones
Research Scientist → 16 Milestones
Lawyer → 15 Milestones
Chartered Accountant → 14 Milestones

The roadmap must feel like a complete progression journey.

Every roadmap should include these phases:

Phase 1:
Discovery & Career Awareness

Phase 2:
Foundations & Mindset Building

Phase 3:
Core Skills Development

Phase 4:
Applied Learning

Phase 5:
Projects & Portfolio Building

Phase 6:
Industry Exposure

Phase 7:
Professional Readiness

Phase 8:
Career Launch

Add additional phases if the career requires deeper specialization.

Tone:

- Student-friendly
- Inspirational
- Future-focused
- Motivational
- Personalized

Use "You" and "We".

Avoid generic career advice.

For EACH roadmap milestone include:

1. Action Name
   - Catchy
   - Motivational
   - Career-specific

2. Stage
   Example:
   Foundations
   Core Skills
   Portfolio Building
   Career Launch

3. Description
   - 3-5 personalized sentences
   - Explain WHY this milestone matters
   - Connect it to student's personality and archetype
   - Explain how it moves them closer to becoming a {path_req.career_title}

4. Skills To Acquire
   - 4 to 6 highly relevant skills

5. Resources

MUST provide exactly 3 resources.

Each resource MUST be:

{{
"name": "...",
"url": "...",
"type": "youtube/course/documentation/article",
"difficulty": "Beginner/Intermediate/Advanced"
}}

Rules:

- Prefer Official Documentation
- Coursera
- DeepLearning.AI
- MIT OpenCourseWare
- Stanford Online
- Harvard Online
- Google Learning
- Microsoft Learn
- IBM SkillsBuild
- Udemy Best Sellers

Never generate fake URLs.

6. Student Project

Must contain:

{{
"name": "...",
"description": "...",
"tools": ["...", "..."],
"parameters": ["...", "..."],
"difficulty": "...",
"portfolio_value": "..."
}}

Project Requirements:

- Step 1 projects should be beginner-friendly
- Difficulty must progressively increase
- Final projects should be industry-level
- Projects should be portfolio-worthy

7. Detailed Task

Provide a precise action plan.

Bad Example:
"Learn Python"

Good Example:
"Complete Python fundamentals including loops, functions, OOP, exception handling and build three mini projects."

8. Timeline

Examples:

"Weeks 1-2"
"Months 1-3"
"Months 4-6"

Provide realistic estimates.

9. Gamification

Provide:

{{
"xp_points": 100,
"achievement_badge": "...",
"unlocks": "..."
}}

10. CareerBuddy Prompt

Generate a contextual AI mentor prompt:

Example:

"Review my first machine learning project and suggest improvements."

Additional Career Insights:

Internships:

Provide 3 dream internships or entry-level roles.

Format:

{{
"title": "...",
"why_it_matters": "..."
}}

Career Outlook:

Provide:

- Salary Journey
- Entry Level Salary
- Mid Level Salary
- Senior Level Salary
- Leadership Level Salary
- Top 5 Companies
- Hiring Trends
- Future Scope
- Automation Risk
- Global Opportunities

Hiring Trends:

Provide a detailed paragraph explaining:

- Current demand
- Recruiter expectations
- Most hired roles
- Important certifications
- Emerging skills

Future Scope:

Explain why this field will or will not grow over the next decade.

Success Metrics:

Generate measurable success indicators.

Examples:

- Complete 5 projects
- Earn AWS Certification
- Reach 500 GitHub Contributions
- Publish Portfolio Website

OUTPUT FORMAT (VALID JSON ONLY):

{{
  "career_title": "{path_req.career_title}",
  "career_complexity": "...",
  "estimated_total_duration": "...",
  "total_milestones": 0,

  "path_steps": [
    {{
      "step": 1,
      "stage": "...",
      "action": "...",
      "description": "...",
      "skills": ["...", "..."],
      "courses": [
        {{
          "name": "...",
          "url": "...",
          "type": "...",
          "difficulty": "..."
        }}
      ],
      "project": {{
        "name": "...",
        "description": "...",
        "tools": [],
        "parameters": [],
        "difficulty": "...",
        "portfolio_value": "..."
      }},
      "detailed_task": "...",
      "timeline": "...",
      "xp_points": 100,
      "achievement_badge": "...",
      "unlocks": "...",
      "careerbuddy_prompt": "...",
      "completed": false
    }}
  ],

  "internships": [],

  "career_outlook": {{
    "salary_journey": {{
      "entry_level": "...",
      "mid_level": "...",
      "senior_level": "...",
      "leadership_level": "..."
    }},
    "top_companies": [],
    "hiring_trends": "...",
    "future_scope": "...",
    "automation_risk": "...",
    "global_opportunities": "..."
  }},

  "success_metrics": [],

  "motivational_message": "..."
}}

Return ONLY VALID JSON.
No markdown.
No explanations.
No text outside JSON.
"""


    try:
        clean_text = await generate_content_with_fallback(prompt)
        path_data = json.loads(clean_text)
        
        # Save to DB
        new_path = models.CareerPath(
            user_id=user.id,
            career_title=path_data.get("career_title", path_req.career_title),
            path_data=path_data.get("path_steps", []),
            reminders=path_data.get("reminders", []),
            # We can store the extra info in the path_data or reminders, 
            # but let's keep it clean by putting everything in one JSON if possible, 
            # or use path_data for the core steps and add a new column if needed.
            # Actually, I'll put the career_outlook and internships into the reminders or a new field if I update the model.
            # Let's update the model to have a general 'meta_data' field or just expand path_data.
        )
        # To avoid database schema migration immediately, I'll wrap everything into path_data
        # and reminders.
        
        # Merge outlook into reminders as a special entry if needed, or just keep it in path_data.
        # Let's put everything extra into a special 'extra_info' key in path_data or just use JSON column flexibility.
        
        full_path_data = {
            "steps": path_data.get("path_steps", []),
            "internships": path_data.get("internships", []),
            "career_outlook": path_data.get("career_outlook", {}),
            "reminders": path_data.get("reminders", [])
        }
        
        new_path.path_data = full_path_data
        
        db.add(new_path)
        await db.commit()
        await db.refresh(new_path)

        return {"success": True, "path_id": new_path.id}
    except Exception as e:
        print(f"Career Path Generation Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate career path: {str(e)}")

@app.post("/career/roadmap/{path_id}/step/{step_index}/toggle")
async def toggle_step_completion(path_id: int, step_index: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    
    # Update path_data
    data = path.path_data
    if data is None:
        raise HTTPException(status_code=400, detail="Path data is empty")

    steps = []
    if isinstance(data, dict) and "steps" in data:
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
    else:
        # Fallback for unexpected format
        raise HTTPException(status_code=400, detail="Invalid path data format")

    if 0 <= step_index < len(steps):
        # Toggle completed state
        is_completed = steps[step_index].get("completed", False)
        steps[step_index]["completed"] = not is_completed
        
        # Update progress percentage if it's a dict with steps
        if isinstance(data, dict) and "steps" in data:
            completed_count = sum(1 for s in data["steps"] if s.get("completed", False))
            data["progress_percentage"] = int((completed_count / len(data["steps"])) * 100)
    else:
        raise HTTPException(status_code=400, detail="Invalid step index")
    
    path.path_data = data
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(path, "path_data")
    
    db.add(path) # Ensure it's in the session correctly
    await db.commit()
    await db.refresh(path)
    
    return {
        "success": True, 
        "completed": steps[step_index]["completed"], 
        "progress": data.get("progress_percentage", 0) if isinstance(data, dict) else 0
    }

@app.get("/career/roadmaps", response_class=HTMLResponse)
async def view_roadmaps(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    paths = (await db.execute(select(models.CareerPath).where(models.CareerPath.user_id == user.id))).scalars().all()
    return templates.TemplateResponse(request=request, name="career_roadmaps.html", context={"user": user, "paths": paths})

ROADMAP_STEP_SYSTEM_PROMPT = """
You are CareerBuddy, an encouraging, motivating, and highly professional AI Career Mentor.

The student is currently sharing progress updates for a specific milestone in their career roadmap.

CAREER ROADMAP: {career_title}
MILESTONE STEP: {step_action}
STEP DETAILS: {step_task}

YOUR ROLE:
Conduct a short and engaging 5-question mentorship interview focused ONLY on this milestone.

GUIDELINES:
1. Ask ONLY one question at a time.
2. Keep the conversation supportive, positive, and practical.But also be strict while calculating effort percentage.
3. Every question must be relevant to the milestone and may include topics such as:
   - What they learned
   - Challenges they faced
   - Tools or technologies used
   - Confidence level
   - Time invested
   - Progress made
   - Next immediate action
4. Never ask more than 5 questions total.
5. Questions should feel conversational, not robotic or repetitive.
6. Encourage reflection and motivation throughout the interaction.
7. Be precise while Calculating effort percentage. account each detail of student response. Be strict while calculating effort percentage.
8. If user shifts off topic . Redirect student to correct topic and ask questions related to milestone.
9. Do not ask questions related to any other milestone than the current one.
10. If donot find any info related to task or milestone in response then  provide low effort percentage.

FINAL RESPONSE RULES (AFTER THE 5TH USER RESPONSE):
1. Provide:
   - A concise summary of the student’s accomplishments
   - Positive encouragement and recognition
   - Constructive next-step guidance
2. Estimate an effort percentage between 0% and 100% based on:
   - Consistency
   - Depth of understanding
   - Practical implementation
   - Initiative shown
   - Tone of Response
   - Time invested
   
3. Mention the effort percentage naturally in the response.
4. VERY IMPORTANT:
   At the absolute end of the final response, append this exact format:

[EFFORT: XX%]

Example:
[EFFORT: 85%]

5. Do NOT include the [EFFORT: XX%] tag in earlier responses.
6. If the effort percentage you calculated is less than 60%, advise the student to look back at this step, spend more time on it, and explain that the next milestone will remain locked until they show greater effort (>= 60%).
"""

class RoadmapStepChatRequest(BaseModel):
    message: str = ""
    answers: list = []

@app.get("/career/roadmap/{path_id}/step/{step_index}/chat", response_class=HTMLResponse)
async def roadmap_step_chat_page(path_id: int, step_index: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    data = path.path_data
    steps = []
    if isinstance(data, dict) and "steps" in data:
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
        
    if not (0 <= step_index < len(steps)):
        raise HTTPException(status_code=404, detail="Step not found")
        
    if step_index > 0:
        previous_step = steps[step_index - 1]
        if not previous_step.get("completed", False) or previous_step.get("effort_percentage", 100) < 60:
            return RedirectResponse(url=f"/career/roadmap/{path_id}", status_code=status.HTTP_302_FOUND)
        
    step = steps[step_index]
    return templates.TemplateResponse(request=request, name="roadmap_step_chat.html", context={
        "user": user,
        "path": path,
        "step_index": step_index,
        "step": step
    })

@app.post("/career/roadmap/{path_id}/step/{step_index}/chat/message")
async def roadmap_step_chat_message(path_id: int, step_index: int, request: Request, chat_req: RoadmapStepChatRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    data = path.path_data
    steps = []
    if isinstance(data, dict) and "steps" in data:
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
        
    if not (0 <= step_index < len(steps)):
         raise HTTPException(status_code=404, detail="Step not found")
         
    if step_index > 0:
        previous_step = steps[step_index - 1]
        if not previous_step.get("completed", False) or previous_step.get("effort_percentage", 100) < 60:
            raise HTTPException(status_code=400, detail="Previous step is not completed or effort was less than 60%. Please redo it.")
         
    step = steps[step_index]
    
    # Build prompt
    system_prompt = ROADMAP_STEP_SYSTEM_PROMPT.format(
        career_title=path.career_title,
        step_action=step.get("action", ""),
        step_task=step.get("detailed_task", "")
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history
    if chat_req.answers:
        for msg in chat_req.answers:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
                
    # Add current user message
    if chat_req.message.strip():
        messages.append({"role": "user", "content": chat_req.message})
        
    user_msg_count = sum(1 for m in chat_req.answers if m.get("role") == "user")
    if chat_req.message.strip():
        user_msg_count += 1
        
    ai_text = ""
    try:
        gclient = get_groq_client()
        if gclient:
            completion = await gclient.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=300,
            )
            ai_text = completion.choices[0].message.content
        elif GEMINI_API_KEY:
            flat_prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
            ai_text = await generate_content_with_fallback(flat_prompt)
        else:
            ai_text = "I am ready to help you complete this milestone! Share your progress with me."
    except Exception as e:
        ai_text = f"Let's discuss your progress on this milestone step! Tell me what you have completed so far."

    # Mark ready on the 5th user message
    recommendation_ready = user_msg_count >= 5
    
    if recommendation_ready:
        import re
        import random
        match = re.search(r"\[EFFORT:\s*(\d+)%\]", ai_text)
        if match:
            effort_score = int(match.group(1))
        else:
            effort_score = random.randint(70, 95)
            
        # Clean tracking tag from response
        ai_text = re.sub(r"\[EFFORT:\s*\d+%\]", "", ai_text).strip()
        
        # Save effort score to the step dictionary
        step["effort_percentage"] = effort_score
        path.path_data = data
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(path, "path_data")
        db.add(path)
        await db.commit()
    
    return {
        "response": ai_text,
        "recommendation_ready": recommendation_ready
    }

@app.post("/career/roadmap/{path_id}/step/{step_index}/chat/finalize")
async def roadmap_step_chat_finalize(path_id: int, step_index: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    data = path.path_data
    steps = []
    if isinstance(data, dict) and "steps" in data:
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
        
    if 0 <= step_index < len(steps):
        steps[step_index]["completed"] = True
        
        # Update progress percentage
        if isinstance(data, dict) and "steps" in data:
            completed_count = sum(1 for s in data["steps"] if s.get("completed", False))
            data["progress_percentage"] = int((completed_count / len(data["steps"])) * 100)
            
        path.path_data = data
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(path, "path_data")
        
        db.add(path)
        await db.commit()
        await db.refresh(path)
        
    return {"redirect": f"/career/roadmap/{path_id}"}

@app.get("/career/roadmap/{path_id}", response_class=HTMLResponse)
async def view_roadmap_detail(path_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    assessment = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()
    appointments = (await db.execute(select(models.Appointment).where(models.Appointment.student_id == user.id))).scalars().all()
        
    return templates.TemplateResponse(request=request, name="career_roadmap_v2.html", context={
        "user": user, 
        "path": path,
        "assessment": assessment,
        "appointments": appointments
    })



@app.get("/career/roadmap/{path_id}/resources", response_class=HTMLResponse)
async def view_roadmap_resources(path_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    path = (await db.execute(select(models.CareerPath).where(models.CareerPath.id == path_id, models.CareerPath.user_id == user.id))).scalars().first()
    if not path:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    career_title = path.career_title
    keywords = career_keywords.get(career_title, [career_title]) # Fallback to title if not in keywords mapping
    
    resources = {
        "ndli": ResourceAggregator.get_ndli_link(keywords),
        "arxiv": ResourceAggregator.get_arxiv_link(keywords),
        "youtube": ResourceAggregator.get_youtube_link(keywords),
        "scholar": ResourceAggregator.get_google_scholar_link(keywords)
    }
    
    # NEW: Fetch AI recommendations
    ai_recommendations = await ResourceAggregator.get_ai_recommendations(career_title, generate_content_with_fallback)
    
    return templates.TemplateResponse(request=request, name="resources_dashboard.html", context={
        "user": user, 
        "path": path,
        "resources": resources,
        "ai_recommendations": ai_recommendations,
        "keywords": keywords
    })

# --- College Recommendation Routes ---

class CollegeRecRequest(BaseModel):
    career_title: str

@app.post("/career/colleges/generate")
async def generate_college_recommendations(request: Request, req: CollegeRecRequest, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (await db.execute(select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id))).scalars().first()

    current_class = result.selected_class if result else "12th"
    archetype = result.phase_2_category if result else "Explorer"
    personality = result.personality if result else "Ambivert"

    prompt = f"""
    You are an expert 'College Admission Strategist' and Academic Mentor for Indian students.

    🎯 OBJECTIVE:
    Recommend the Top 5 colleges/institutes located ONLY in India that are BEST suited for the student profile below.

    🚫 STRICT EXCLUSION:
    DO NOT include IITs, NITs, IIITs, IIMs, AIIMS, IISc, or any top-tier elite institutions.
    Focus on strong Tier-2 / Tier-3 colleges that provide good ROI, practical exposure, and career growth.

    👤 STUDENT PROFILE:
    - Current Stage: {current_class}
    - Archetype: {archetype}
    - Personality: {personality}
    - Target Career: {req.career_title}

    🧠 PERSONALIZATION REQUIREMENT:
    Match colleges based on:
    - Teaching style (practical vs theoretical)
    - Campus culture (competitive vs collaborative)
    - Student personality fit (introvert/extrovert, structured/creative)
    - Growth opportunities (internships, exposure, startup culture)

    📌 TASK:
    For EACH college, provide REALISTIC and FACTUALLY GROUNDED details:

    1. "name" — Full official name
    2. "location" — City, India
    3. "ranking" — Relative positioning (e.g., "Top Private College in North India", avoid fake global ranks)
    4. "admission_criteria" — Exams accepted, eligibility, approximate cutoffs, and admission process (3-4 sentences, realistic)
    5. "courses_offered" — 3–5 relevant programs aligned with the career
    6. "placement_rate" — Realistic estimate (avoid 100% claims unless justified)
    7. "avg_package" — Realistic average package range (in INR LPA)
    8. "top_recruiters" — 3–4 commonly known recruiters (avoid exaggeration)
    9. "highlights" — Why this college is a GOOD FIT for THIS student's archetype and personality (VERY IMPORTANT)
    10. "website" — Official website URL

    ⚠️ IMPORTANT RULES:
    - Do NOT hallucinate rankings or unrealistic salary figures
    - Prefer well-known but non-elite institutions (e.g., VIT, SRM, Manipal, etc.)
    - Ensure diversity (different states / types of colleges)
    - Ensure explanation clearly connects to student personality

    📦 OUTPUT FORMAT (STRICT JSON ONLY — NO EXTRA TEXT):
    {{
      "colleges": [
        {{
          "name": "...",
          "location": "...",
          "ranking": "...",
          "admission_criteria": "...",
          "courses_offered": ["...", "...", "..."],
          "placement_rate": "...",
          "avg_package": "...",
          "top_recruiters": ["...", "...", "..."],
          "highlights": "...",
          "website": "https://..."
        }}
      ],
      "preparation_tips": ["...", "...", "...", "..."]
    }}

    🎯 PREPARATION TIPS:
    Provide 3–4 highly practical and actionable tips tailored to this student profile (not generic advice).
    """

    try:
        clean_text = await generate_content_with_fallback(prompt)
        college_data = json.loads(clean_text)

        new_rec = models.CollegeRecommendation(
            user_id=user.id,
            career_title=req.career_title,
            college_data=college_data,
        )
        db.add(new_rec)
        await db.commit()
        await db.refresh(new_rec)

        return {"success": True, "rec_id": new_rec.id}
    except Exception as e:
        print(f"College Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate college recommendations: {str(e)}")


@app.get("/career/colleges", response_class=HTMLResponse)
async def view_college_recommendations(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    recs = (await db.execute(select(models.CollegeRecommendation).where(models.CollegeRecommendation.user_id == user.id).order_by(models.CollegeRecommendation.created_at.desc()))).scalars().all()
    return templates.TemplateResponse(request=request, name="college_recommendations.html", context={"user": user, "recs": recs})


@app.get("/career/colleges/{rec_id}", response_class=HTMLResponse)
async def view_college_detail(rec_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    rec = (await db.execute(
        select(models.CollegeRecommendation).where(
            models.CollegeRecommendation.id == rec_id,
            models.CollegeRecommendation.user_id == user.id
        )
    )).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="College recommendation not found")

    return templates.TemplateResponse(request=request, name="college_detail.html", context={"user": user, "rec": rec})


# ─── Student Community & Connection Routes ────────────────────────────────────

@app.get("/community", response_class=HTMLResponse)
async def community_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Community page: discover students grouped by archetype."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Get current user's archetype
    my_assessment = (await db.execute(
        select(models.AssessmentResult).where(
            models.AssessmentResult.user_id == user.id
        )
    )).scalars().first()
    my_archetype = my_assessment.phase_2_category if my_assessment else None

    # Get all students (except current user) who have completed their assessment
    _rows = (await db.execute(
        select(models.User, models.AssessmentResult)
        .join(models.AssessmentResult, models.User.id == models.AssessmentResult.user_id)
        .where(
            models.User.role == "student",
            models.User.id != user.id,
            models.AssessmentResult.phase_2_category.isnot(None)
        )
    )).all()
    students_with_assessments = [(row[0], row[1]) for row in _rows]

    # Build connection status map for current user
    my_connections = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                models.StudentConnection.requester_id == user.id,
                models.StudentConnection.receiver_id == user.id
            )
        )
    )).scalars().all()

    connection_map = {}  # user_id -> {"status": ..., "conn_id": ..., "is_requester": bool}
    for conn in my_connections:
        other_id = conn.receiver_id if conn.requester_id == user.id else conn.requester_id
        connection_map[other_id] = {
            "status": conn.status,
            "conn_id": conn.id,
            "is_requester": conn.requester_id == user.id
        }

    # Group students by archetype
    similar_students = []
    other_archetypes = {}
    for student, assessment in students_with_assessments:
        student_data = {
            "user": student,
            "assessment": assessment,
            "connection": connection_map.get(student.id)
        }
        if my_archetype and assessment.phase_2_category == my_archetype:
            similar_students.append(student_data)
        else:
            archetype = assessment.phase_2_category
            if archetype not in other_archetypes:
                other_archetypes[archetype] = []
            other_archetypes[archetype].append(student_data)

    # Count pending received requests
    pending_count = (await db.execute(
        select(func.count()).select_from(models.StudentConnection).where(
            models.StudentConnection.receiver_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalar() or 0

    return templates.TemplateResponse(request=request, name="community.html", context={
        "user": user,
        "my_archetype": my_archetype,
        "similar_students": similar_students,
        "other_archetypes": other_archetypes,
        "pending_count": pending_count,
    })


@app.get("/student/{user_id}", response_class=HTMLResponse)
async def student_profile(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Public profile page for a student."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    student = (await db.execute(
        select(models.User).where(
            models.User.id == user_id,
            models.User.role == "student"
        )
    )).scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    assessment = (await db.execute(
        select(models.AssessmentResult).where(
            models.AssessmentResult.user_id == user_id
        )
    )).scalars().first()

    # Connection status between current user and this student
    connection = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                and_(models.StudentConnection.requester_id == user.id, models.StudentConnection.receiver_id == user_id),
                and_(models.StudentConnection.requester_id == user_id, models.StudentConnection.receiver_id == user.id)
            )
        )
    )).scalars().first()

    conn_info = None
    if connection:
        conn_info = {
            "status": connection.status,
            "conn_id": connection.id,
            "is_requester": connection.requester_id == user.id
        }

    # Get this student's accepted connections (for sidebar)
    accepted_connections = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                models.StudentConnection.requester_id == user_id,
                models.StudentConnection.receiver_id == user_id
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().all()

    connected_users = []
    for conn in accepted_connections:
        other_id = conn.receiver_id if conn.requester_id == user_id else conn.requester_id
        other_user = (await db.execute(select(models.User).where(models.User.id == other_id))).scalars().first()
        if other_user:
            connected_users.append(other_user)

    is_own_profile = (user.id == user_id)

    return templates.TemplateResponse(request=request, name="student_profile.html", context={
        "user": user,
        "student": student,
        "assessment": assessment,
        "connection": conn_info,
        "connected_users": connected_users,
        "is_own_profile": is_own_profile,
    })


@app.post("/connect/{user_id}")
async def send_connection_request(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Send a connection request to another student."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if user.id == user_id:
        return RedirectResponse(url="/community", status_code=status.HTTP_302_FOUND)

    # Check receiver exists and is a student
    receiver = (await db.execute(select(models.User).where(models.User.id == user_id, models.User.role == "student"))).scalars().first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Student not found")

    # Check for existing connection
    existing = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                and_(models.StudentConnection.requester_id == user.id, models.StudentConnection.receiver_id == user_id),
                and_(models.StudentConnection.requester_id == user_id, models.StudentConnection.receiver_id == user.id)
            )
        )
    )).scalars().first()

    if existing:
        # Already exists – redirect back
        referer = request.headers.get("referer", "/community")
        return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)

    new_conn = models.StudentConnection(requester_id=user.id, receiver_id=user_id, status="pending")
    db.add(new_conn)
    await db.commit()

    # Send Email Notification
    try:
        app_url = os.getenv("APP_URL", str(request.base_url).rstrip("/"))
        profile_link = f"{app_url}/student/{user.id}"
        email_body = email_utils.get_connection_request_template(
            receiver.full_name, 
            user.full_name, 
            profile_link
        )
        email_utils.send_email(receiver.email, f"New Connection Request from {user.full_name}", email_body)
    except Exception as e:
        print(f"FAILED TO SEND CONNECTION EMAIL: {e}")

    referer = request.headers.get("referer", "/community")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.post("/connection/{conn_id}/accept")
async def accept_connection(conn_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Accept a pending connection request."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            models.StudentConnection.receiver_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalars().first()

    if not conn:
        raise HTTPException(status_code=404, detail="Connection request not found")

    conn.status = "accepted"
    await db.commit()

    referer = request.headers.get("referer", "/my-connections")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.post("/connection/{conn_id}/reject")
async def reject_connection(conn_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Reject a pending connection request."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            models.StudentConnection.receiver_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalars().first()

    if not conn:
        raise HTTPException(status_code=404, detail="Connection request not found")

    await db.delete(conn)
    await db.commit()

    referer = request.headers.get("referer", "/my-connections")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.post("/connection/{conn_id}/withdraw")
async def withdraw_connection(conn_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Withdraw a pending connection request sent by the current user."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            models.StudentConnection.requester_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalars().first()

    if not conn:
        raise HTTPException(status_code=404, detail="Connection request not found or cannot be withdrawn")

    await db.delete(conn)
    await db.commit()

    referer = request.headers.get("referer", "/community")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.post("/disconnect/{user_id}")
async def disconnect_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Remove an existing connection."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    conn = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                and_(models.StudentConnection.requester_id == user.id, models.StudentConnection.receiver_id == user_id),
                and_(models.StudentConnection.requester_id == user_id, models.StudentConnection.receiver_id == user.id)
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().first()

    if conn:
        await db.delete(conn)
        await db.commit()

    referer = request.headers.get("referer", "/community")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.post("/profile/update-bio")
async def update_bio(request: Request, bio: str = Form(""), db: AsyncSession = Depends(get_db)):
    """Update the current user's bio."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    user.bio = bio.strip()[:500]  # Limit to 500 chars
    await db.commit()

    referer = request.headers.get("referer", "/dashboard")
    return RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)


@app.get("/my-connections", response_class=HTMLResponse)
async def my_connections_page(request: Request, db: AsyncSession = Depends(get_db)):
    """View accepted connections and pending requests."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Accepted connections
    accepted = (await db.execute(
        select(models.StudentConnection).where(
            or_(
                models.StudentConnection.requester_id == user.id,
                models.StudentConnection.receiver_id == user.id
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().all()

    connected_users = []
    for conn in accepted:
        other_id = conn.receiver_id if conn.requester_id == user.id else conn.requester_id
        other_user = (await db.execute(select(models.User).where(models.User.id == other_id))).scalars().first()
        if other_user:
            other_assessment = (await db.execute(
                select(models.AssessmentResult).where(
                    models.AssessmentResult.user_id == other_id
                )
            )).scalars().first()
            connected_users.append({
                "user": other_user,
                "assessment": other_assessment,
                "conn_id": conn.id
            })

    # Pending received requests
    pending_received = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.receiver_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalars().all()

    pending_requests = []
    for conn in pending_received:
        requester = (await db.execute(select(models.User).where(models.User.id == conn.requester_id))).scalars().first()
        if requester:
            req_assessment = (await db.execute(
                select(models.AssessmentResult).where(
                    models.AssessmentResult.user_id == conn.requester_id
                )
            )).scalars().first()
            pending_requests.append({
                "user": requester,
                "assessment": req_assessment,
                "conn_id": conn.id
            })

    # Pending sent requests
    pending_sent = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.requester_id == user.id,
            models.StudentConnection.status == "pending"
        )
    )).scalars().all()

    sent_requests = []
    for conn in pending_sent:
        receiver = (await db.execute(select(models.User).where(models.User.id == conn.receiver_id))).scalars().first()
        if receiver:
            sent_requests.append({
                "user": receiver,
                "conn_id": conn.id
            })

    return templates.TemplateResponse(request=request, name="my_connections.html", context={
        "user": user,
        "connected_users": connected_users,
        "pending_requests": pending_requests,
        "sent_requests": sent_requests,
    })


@app.get("/connection/{conn_id}/chat", response_class=HTMLResponse)
async def student_chat_page(conn_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Private chat page between connected students."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Verify connection exists and is accepted
    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            or_(
                models.StudentConnection.requester_id == user.id,
                models.StudentConnection.receiver_id == user.id
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().first()

    if not conn:
        raise HTTPException(status_code=403, detail="Not connected or unauthorized")

    other_id = conn.receiver_id if conn.requester_id == user.id else conn.requester_id
    other_user = (await db.execute(select(models.User).where(models.User.id == other_id))).scalars().first()

    # Get message history
    messages = (await db.execute(
        select(models.StudentMessage).where(
            or_(
                and_(models.StudentMessage.sender_id == user.id, models.StudentMessage.receiver_id == other_id),
                and_(models.StudentMessage.sender_id == other_id, models.StudentMessage.receiver_id == user.id)
            )
        ).order_by(models.StudentMessage.timestamp.asc())
    )).scalars().all()

    # Mark as read
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(models.StudentMessage)
        .where(
            models.StudentMessage.receiver_id == user.id,
            models.StudentMessage.sender_id == other_id,
            models.StudentMessage.is_read == False
        )
        .values(is_read=True)
    )
    await db.commit()

    try:
        template = templates.get_template("student_chat.html")
        content = template.render({
            "request": request, 
            "user": user, 
            "other_user": other_user,
            "messages": messages,
            "conn_id": conn_id
        })
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)


@app.post("/connection/{conn_id}/chat/send")
async def send_student_message(
    conn_id: int, 
    request: Request, 
    content: str = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Send a private message to a connected student."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    if user.is_suspended:
        return RedirectResponse(url="/suspended", status_code=status.HTTP_302_FOUND)

    # If JSON request (XHR)
    if request.headers.get("content-type") == "application/json":
        data = await request.json()
        content = data.get("content")

    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")

    # Verify connection
    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            or_(
                models.StudentConnection.requester_id == user.id,
                models.StudentConnection.receiver_id == user.id
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().first()

    if not conn:
        raise HTTPException(status_code=403, detail="Not connected or unauthorized")

    receiver_id = conn.receiver_id if conn.requester_id == user.id else conn.requester_id

    # Moderation Check
    is_flagged, reason = await check_content_moderation(content)
    if is_flagged:
        flag = models.ModerationFlag(user_id=user.id, content=content, chat_type="p2p", status="pending_review")
        db.add(flag)
        await db.commit()
        # For P2P we return an error state
        if request.headers.get("content-type") == "application/json":
            return {"error": "Your message was flagged as inappropriate. Repeated violations will lead to account suspension."}
        return RedirectResponse(url=f"/connection/{conn_id}/chat?error=flagged", status_code=status.HTTP_302_FOUND)

    attachment_path = None
    attachment_type = None

    if file:
        try:
            upload_dir = os.path.join(STATIC_DIR, "uploads", "chat")
            os.makedirs(upload_dir, exist_ok=True)
            
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            attachment_path = f"/static/uploads/chat/{unique_filename}"
            attachment_type = "image" if file.content_type.startswith("image") else "file"
            
            # If no content, use filename
            if not content:
                content = file.filename
        except Exception as e:
            print(f"File upload error: {e}")

    new_msg = models.StudentMessage(
        sender_id=user.id,
        receiver_id=receiver_id,
        content=content,
        attachment_path=attachment_path,
        attachment_type=attachment_type
    )
    db.add(new_msg)
    await db.commit()

    if request.headers.get("content-type") == "application/json":
        return {"success": True, "message_id": new_msg.id}

    return RedirectResponse(url=f"/connection/{conn_id}/chat", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/connection/{conn_id}/chat/messages")
async def get_student_messages(conn_id: int, request: Request, after_id: int = 0, db: AsyncSession = Depends(get_db)):
    """Fetch new messages for real-time polling."""
    user = await get_current_user(request, db)
    if not user:
        return {"error": "Unauthorized"}

    conn = (await db.execute(
        select(models.StudentConnection).where(
            models.StudentConnection.id == conn_id,
            or_(
                models.StudentConnection.requester_id == user.id,
                models.StudentConnection.receiver_id == user.id
            ),
            models.StudentConnection.status == "accepted"
        )
    )).scalars().first()

    if not conn:
        return {"error": "Forbidden"}

    other_id = conn.receiver_id if conn.requester_id == user.id else conn.requester_id

    messages = (await db.execute(
        select(models.StudentMessage).where(
            or_(
                and_(models.StudentMessage.sender_id == user.id, models.StudentMessage.receiver_id == other_id),
                and_(models.StudentMessage.sender_id == other_id, models.StudentMessage.receiver_id == user.id)
            ),
            models.StudentMessage.id > after_id
        ).order_by(models.StudentMessage.timestamp.asc())
    )).scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "content": m.content,
                "attachment_path": m.attachment_path,
                "attachment_type": m.attachment_type,
                "timestamp": m.timestamp.isoformat()
            }
            for m in messages
        ]
    }


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    try:
        template = templates.get_template("privacy.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    try:
        template = templates.get_template("terms.html")
        content = template.render({"request": request, "user": user})
        return HTMLResponse(content=content)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"Template Error: {e}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/debug/migrate")
async def debug_migrate(request: Request, db: AsyncSession = Depends(get_db)):
    """Manually trigger migrations and return status."""
    try:
        await run_migrations()
        return {"status": "success", "message": "Migrations triggered. Check console/logs for details."}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

if __name__ == "__main__":
    import uvicorn
    dev_reload = os.getenv("DEV_RELOAD", "false").strip().lower() in ("1", "true", "yes")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=dev_reload,
    )