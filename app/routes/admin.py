"""
Admin Panel Router
All routes are protected by the get_current_admin dependency.
"""
from __future__ import annotations

import logging
import csv
import os
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.database import get_db
from app.models import CounsellorProfile, ModerationFlag, Payment, SimulationPayment, Ticket, User
from app.dependencies.admin_auth import get_current_admin
from app.models import AssessmentResult
from sqlalchemy import func, select

from app.services.admin_user_service import (
    get_all_users,
    get_user_by_id,
    block_user,
    unblock_user,
    reset_user_password,
)

from app.appwrite_helper import get_user_by_email
from app.services.admin_feedback_service import (
    get_feedback_logs,
    get_support_tickets,
    update_ticket_status,
)
from app.services.admin_counsellor_service import (
    get_pending_counsellors,
    get_all_counsellors,
    approve_counsellor,
    reject_counsellor,
    block_counsellor,
    unblock_counsellor,
    get_counsellor_session_analytics,
)
from app.services.admin_payment_service import (
    get_payment_analytics,
    get_recent_payment_logs,
    get_recent_simulation_payments,
)
from app.services.admin_analytics_service import (
    get_recent_appointments,
    get_moderation_flags,
    resolve_moderation_flag,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="frontend/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _redirect_back(request: Request, default: str = "/admin") -> RedirectResponse:
    return RedirectResponse(
        url=request.headers.get("referer") or default,
        status_code=303,
    )


def _normalize_career_recommendations(assessment: AssessmentResult | None) -> list[dict]:
    """Return a stable recommendation list for old and new assessment reports."""
    if not assessment or not assessment.assessment_report:
        return []

    report = assessment.assessment_report
    raw_recommendations = report.get("final_recommendations") or report.get("recommendations") or []
    if not raw_recommendations:
        raw_recommendations = report.get("top_careers") or []

    normalized = []
    for item in raw_recommendations[:3]:
        if not isinstance(item, dict):
            continue
        title = item.get("career") or item.get("title") or item.get("career_title") or "Career option"
        score = (
            item.get("confidence_score")
            if item.get("confidence_score") is not None
            else item.get("match_score", item.get("score"))
        )
        try:
            score_float = float(score)
        except (TypeError, ValueError):
            score_float = 0.0
        if score_float > 1:
            score_float = score_float / 100

        normalized.append(
            {
                "career": title,
                "confidence_score": max(0.0, min(score_float, 1.0)),
                "feasibility_status": item.get("feasibility_status") or item.get("fit_status") or "Optimal Fit",
                "notes": item.get("pivot_notes") or item.get("description") or item.get("summary") or "",
            }
        )

    return normalized


# ─── Main Dashboard ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    user_page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_search: str = Query(None),
    counsellor_search: str = Query(None),
    feedback_page: int = Query(1, ge=1),
    ticket_page: int = Query(1, ge=1),
):
    """Main admin dashboard — fetches all modules and renders template."""
    try:
        # Parallel-ish fetches (sequential but separated for clarity)
        users_data = await get_all_users(db, page=user_page, page_size=page_size, search=user_search)
        user_ids_on_page = [u.id for u in users_data["users"]]
        assessments_map = {}
        assessment_summaries = {}
        if user_ids_on_page:
            ar_rows = (await db.execute(
                select(AssessmentResult).where(AssessmentResult.user_id.in_(user_ids_on_page))
            )).scalars().all()
            assessments_map = {ar.user_id: ar for ar in ar_rows}
            assessment_summaries = {
                ar.user_id: {
                    "career_recommendations": _normalize_career_recommendations(ar),
                    "pipeline_version": (ar.assessment_report or {}).get("pipeline_version"),
                }
                for ar in ar_rows
            }
        feedback_data = await get_feedback_logs(db, page=feedback_page, page_size=page_size)
        tickets_data = await get_support_tickets(db, page=ticket_page, page_size=page_size)
        pending_counsellors = await get_pending_counsellors(db)
        counsellors_data = await get_all_counsellors(db, search=counsellor_search)
        counsellor_analytics = await get_counsellor_session_analytics(db)
        counsellor_analytics_map = {
            row["counsellor_id"]: row for row in counsellor_analytics
        }
        appointments = await get_recent_appointments(db)
        payment_analytics = await get_payment_analytics(db)
        payment_logs = await get_recent_payment_logs(db)
        simulation_payments = await get_recent_simulation_payments(db)
        mod_flags = await get_moderation_flags(db)
        captured_count = (await db.execute(
            select(func.count(Payment.id)).where(Payment.status == "captured")
        )).scalar_one()
        sim_count = (await db.execute(
            select(func.count(SimulationPayment.id)).where(SimulationPayment.status.in_(["success", "captured"]))
        )).scalar_one()
      
        return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "admin": admin,
            "users": users_data["users"],
            "assessments": assessments_map,
            "assessment_summaries": assessment_summaries,
            "users_pagination": {
                "page": users_data["page"],
                "page_size": users_data["page_size"],
                "total": users_data["total"],
                "total_pages": users_data["total_pages"],
            },
            "feedback_logs": feedback_data["feedback_logs"],
            "support_tickets": tickets_data["support_tickets"],
            "pending_counsellors": pending_counsellors,
            "counsellors": counsellors_data["counsellors"],
            "counsellor_session_analytics": counsellor_analytics,
            "counsellor_session_analytics_map": counsellor_analytics_map,
            "appointments": appointments,
            "payment_logs": payment_logs,
            "session_revenue": payment_analytics["session_revenue"],
            "simulation_revenue": payment_analytics["simulation_revenue"],
            "total_revenue": payment_analytics["total_revenue"],
            "counsellor_payouts": payment_analytics["counsellor_payouts"],
            "platform_commission": payment_analytics["platform_commission"],
            "pending_payouts": payment_analytics["pending_payouts"],
            "failed_payouts": payment_analytics["failed_payouts"],
            "moderation_flags": mod_flags,
            "pending_transfers": payment_analytics["pending_payouts"],
            "failed_transfers": payment_analytics["failed_payouts"],

            "all_payments": payment_logs,
            "all_appointments": appointments,
            "all_counsellors": counsellors_data["counsellors"],
            "user_search": user_search or "",
            "counsellor_search": counsellor_search or "",
            "user_page": user_page,
            "feedback_page": feedback_page,
            "ticket_page": ticket_page,
            "page_size": page_size,
            "total_users": users_data["total"],
            "total_feedback": feedback_data["total"],
            "total_tickets": tickets_data["total"],
            "feedbacks": feedback_data["feedback_logs"],
            "tickets": tickets_data["support_tickets"],
            "simulation_payments": simulation_payments,
            "captured_payments_count": captured_count,
            "sim_payments_count": sim_count,
        }
    )
    except Exception as e:
        import traceback
        print(f"ADMIN ERROR DETAIL: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── User Management APIs ─────────────────────────────────────────────────────

@router.post("/users/{user_id}/block")
async def api_block_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await block_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"User {user.full_name} blocked successfully.", "user_id": user_id}


@router.post("/users/{user_id}/unblock")
async def api_unblock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await unblock_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"User {user.full_name} unblocked.", "user_id": user_id}


@router.post("/users/{user_id}/suspend")
async def form_suspend_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await block_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _redirect_back(request)


@router.post("/users/{user_id}/unsuspend")
async def form_unsuspend_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await unblock_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _redirect_back(request)


@router.post("/users/{user_id}/delete")
async def form_soft_delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Compatibility route: keep admin-panel deletes as a soft suspension."""
    # Per spec: do not permanently delete users; suspend instead.
    user = await block_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _redirect_back(request)


@router.post("/users/{user_id}/reset-password")
async def api_reset_user_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Reset password in BOTH places:
    1) local DB (User.hashed_password)
    2) Appwrite account password (so login works when Appwrite is the auth source)
    """
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    # bcrypt (via passlib) hard-limits input to 72 bytes.
    # If password is too long, bcrypt will throw ValueError.
    # We truncate deterministically for local hashing (Appwrite update uses full password).
    # bcrypt/passlib enforces 72 BYTES max (not 72 chars). Truncate byte-safe for UTF-8.
    trunc_bytes = new_password.encode("utf-8")[:72]
    # Reconstruct strictly; if boundary splits a multibyte char, fall back to ignore *after* truncation.
    try:
        new_password_local = trunc_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        new_password_local = trunc_bytes.decode("utf-8", errors="ignore")
    hashed = pwd_context.hash(new_password_local)

    # 1) Reset local DB password
    user = await reset_user_password(db, user_id, hashed)
    # (Do not block Appwrite update on local hashing issues; handled above.)

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 2) Reset Appwrite password
    # Appwrite SDK password update requires the Appwrite account id.
    # In this project, signup creates an Appwrite user and stores numeric local_id.
    # We therefore look up the Appwrite user by email and then try common SDK method signatures.
    try:
        appwrite_user = get_user_by_email(user.email)
        appwrite_account_id = None

        # get_user_by_email returns a SimpleNamespace with either 'id' (local_id) or 'appwrite_id'
        # doc_to_model sets: data['appwrite_id'] = data['$id']
        if appwrite_user is not None:
            appwrite_account_id = getattr(appwrite_user, "appwrite_id", None) or getattr(appwrite_user, "id", None)

        if not appwrite_account_id:
            logger.warning(
                "Admin reset password: could not resolve Appwrite account id for local user_id=%s email=%s",
                user_id,
                user.email,
            )
            raise RuntimeError("Appwrite account id not found")

        # Try common Appwrite SDK password update method names/signatures.
        # We keep this defensive because the repo currently has no existing password-update usage.
        from app.appwrite_client import account as appwrite_account

        update_errors: list[str] = []
        methods_tried: list[str] = []

        # Candidate calls
        candidates = [
            ("account.updatePassword(user_id=..., password=...)", lambda: appwrite_account.updatePassword(userId=str(appwrite_account_id), password=new_password)),
            ("account.updatePassword(user_id, password)", lambda: appwrite_account.updatePassword(str(appwrite_account_id), new_password)),
            ("account.updateEmailPassword(user_id=..., password=...)", lambda: appwrite_account.updateEmailPassword(userId=str(appwrite_account_id), password=new_password)),
            ("account.updateEmailPassword(user_id, password)", lambda: appwrite_account.updateEmailPassword(str(appwrite_account_id), new_password)),
        ]

        last_exc: Exception | None = None
        for label, fn in candidates:
            methods_tried.append(label)
            try:
                maybe_res = fn()
                # Some SDK calls might be synchronous; if it returns a coroutine, await it.
                if hasattr(maybe_res, "__await__"):
                    import asyncio
                    await maybe_res
                break
            except Exception as e:
                last_exc = e
                update_errors.append(f"{label}: {e}")
        else:
            # none succeeded
            raise RuntimeError(
                "Appwrite password update failed. "
                + "\n".join(update_errors)
            ) from last_exc

    except Exception as e:
        # If Appwrite update fails, the local password is already updated.
        # But since login prefers Appwrite, we surface the error so admin knows it isn't fully applied.
        logger.error(
            "Admin reset password: Appwrite update failed for user_id=%s email=%s err=%s",
            user_id,
            user.email,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Local password reset succeeded, but Appwrite password update failed: {str(e)}",
        )

    if "text/html" in request.headers.get("accept", ""):
        return _redirect_back(request)
    return {"message": f"Password reset for user {user.full_name} (local + Appwrite).", "user_id": user_id}

# ─── Ticket Management APIs ───────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/status")
async def api_update_ticket_status(
    ticket_id: int,
    status: str,
    admin_reply: str = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        ticket = await update_ticket_status(db, ticket_id, status, admin_reply)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"message": f"Ticket {ticket_id} updated to '{status}'.", "ticket_id": ticket_id}


@router.post("/tickets/{ticket_id}/close")
async def form_close_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ticket = await update_ticket_status(db, ticket_id, "Closed")
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return _redirect_back(request)


@router.post("/tickets/{ticket_id}/set-status")
async def form_set_ticket_status(
    ticket_id: int,
    request: Request,
    status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        ticket = await update_ticket_status(db, ticket_id, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return _redirect_back(request)


@router.post("/tickets/{ticket_id}/reply")
async def form_reply_ticket(
    ticket_id: int,
    request: Request,
    reply_content: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ticket = await update_ticket_status(db, ticket_id, "In Progress", reply_content)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return _redirect_back(request)


@router.post("/tickets/{ticket_id}/delete")
async def form_delete_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ticket = (await db.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    await db.delete(ticket)
    await db.commit()
    return _redirect_back(request)


# ─── Counsellor Management APIs ───────────────────────────────────────────────

@router.post("/counsellors/{profile_id}/approve")
async def api_approve_counsellor(
    profile_id: int,
    remarks: str = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    profile = await approve_counsellor(db, profile_id, remarks)
    if not profile:
        raise HTTPException(status_code=404, detail="Counsellor profile not found.")
    return {"message": "Counsellor approved.", "profile_id": profile_id}


@router.post("/counsellors/{profile_id}/reject")
async def api_reject_counsellor(
    profile_id: int,
    remarks: str = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    profile = await reject_counsellor(db, profile_id, remarks)
    if not profile:
        raise HTTPException(status_code=404, detail="Counsellor profile not found.")
    return {"message": "Counsellor rejected.", "profile_id": profile_id, "remarks": remarks}


@router.post("/verify-counsellor/{counsellor_id}")
async def form_verify_counsellor(
    counsellor_id: int,
    request: Request,
    verification_status: str = Form(...),
    remarks: str = Form(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    profile = (await db.execute(
        select(CounsellorProfile).where(CounsellorProfile.user_id == counsellor_id)
    )).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Counsellor profile not found.")

    if verification_status == "approved":
        await approve_counsellor(db, profile.id, remarks)
    elif verification_status == "rejected":
        await reject_counsellor(db, profile.id, remarks)
    else:
        raise HTTPException(status_code=400, detail="Invalid verification status.")
    return _redirect_back(request)


@router.post("/counsellors/{profile_id}/block")
async def api_block_counsellor(
    profile_id: int,
    reason: str = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    profile = await block_counsellor(db, profile_id, reason)
    if not profile:
        raise HTTPException(status_code=404, detail="Counsellor profile not found.")
    return {"message": "Counsellor blocked.", "profile_id": profile_id}


@router.post("/counsellors/{profile_id}/unblock")
async def api_unblock_counsellor(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    profile = await unblock_counsellor(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Counsellor profile not found.")
    return {"message": "Counsellor unblocked.", "profile_id": profile_id}


# ─── Moderation Flag APIs ─────────────────────────────────────────────────────

@router.post("/moderation/{flag_id}/resolve")
async def api_resolve_flag(
    flag_id: int,
    status: str = Form(...),
    admin_note: str = Form(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        flag = await resolve_moderation_flag(db, flag_id, status, admin_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not flag:
        raise HTTPException(status_code=404, detail="Moderation flag not found.")
    return {"message": f"Flag {flag_id} marked as '{status}'.", "flag_id": flag_id}


@router.post("/flags/{flag_id}/action")
async def form_handle_flag(
    flag_id: int,
    request: Request,
    action: str = Form(...),
    admin_note: str = Form(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    status_map = {
        "reviewed": "dismissed",
        "dismiss": "dismissed",
        "resolved": "action_taken",
        "action_taken": "action_taken",
        "pending_review": "pending_review",
    }
    flag = await resolve_moderation_flag(
        db,
        flag_id,
        status_map.get(action, "pending_review"),
        admin_note,
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Moderation flag not found.")
    return _redirect_back(request)

import csv
import os

# ─── Career Management APIs ───────────────────────────────────────────────────

CSV_PATH = "app/assessment_data/occupation_feature_matrix_1.csv"

@router.get("/careers")
async def get_all_careers(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all careers from CSV."""
    careers = []
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                careers.append({
                    "code": row["O*NET-SOC Code"],
                    "title": row["Title"],
                    "description": row["Description"],
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {str(e)}")
    return {"careers": careers, "total": len(careers)}


@router.post("/careers/add")
async def add_career(
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a new career/occupation to the CSV."""
    data = await request.json()
    
    code = data.get("code", "").strip()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    
    if not code or not title or not description:
        raise HTTPException(status_code=400, detail="code, title, description required.")
    
    # Read existing headers
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            existing = list(reader)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {str(e)}")
    
    # Check duplicate
    for row in existing:
        if row["O*NET-SOC Code"] == code or row["Title"].lower() == title.lower():
            raise HTTPException(status_code=400, detail="Career with this code or title already exists.")
    
    # Build new row — all numeric fields default to 0
    new_row = {h: "0" for h in headers}
    new_row["O*NET-SOC Code"] = code
    new_row["Title"] = title
    new_row["Description"] = description
    new_row["Job Zone"] = data.get("job_zone", "3")
    
    # Optional RIASEC fields
    riasec_map = {
        "IT_Artistic": data.get("artistic", "0"),
        "IT_Conventional": data.get("conventional", "0"),
        "IT_Enterprising": data.get("enterprising", "0"),
        "IT_Investigative": data.get("investigative", "0"),
        "IT_Realistic": data.get("realistic", "0"),
        "IT_Social": data.get("social", "0"),
    }
    new_row.update(riasec_map)
    
    # Append to CSV
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(new_row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing CSV: {str(e)}")
    
    logger.info(f"Admin added new career: {title} ({code})")
    return {"message": f"Career '{title}' added successfully.", "code": code, "title": title}


@router.delete("/careers/{code}")
async def delete_career(
    code: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a career from CSV by O*NET code."""
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {str(e)}")
    
    original_count = len(rows)
    rows = [r for r in rows if r["O*NET-SOC Code"] != code]
    
    if len(rows) == original_count:
        raise HTTPException(status_code=404, detail="Career not found.")
    
    try:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing CSV: {str(e)}")
    
    logger.info(f"Admin deleted career: {code}")
    return {"message": f"Career {code} deleted successfully."}
