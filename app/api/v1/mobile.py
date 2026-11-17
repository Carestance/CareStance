"""Mobile API endpoints backed by CareStance's existing database and services."""

from __future__ import annotations

import datetime
import re
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_db
from app.security import (
    create_access_token,
    decode_access_token,
    get_bearer_token,
    get_password_hash,
    verify_password,
)
from app.services.growth_profile_service import build_growth_profile
from app.services.monthly_plan_service import get_monthly_plan_progress
from app.services.push_notifications import get_vapid_public_key

router = APIRouter(prefix="/api/v1", tags=["mobile"])
MOBILE_TOKEN_LIFETIME = datetime.timedelta(hours=12)
PHONE_PATTERN = re.compile(r"^\+\d{1,3}\s?\d{10}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    contact_number: str
    role: Literal["student", "counsellor"] = "student"


class MobileUser(BaseModel):
    id: int
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    onboarded: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: MobileUser


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=256)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushSubscriptionKeys


class AssessmentStateResponse(BaseModel):
    status: Literal["not_started", "in_progress", "completed"]
    student_type: Optional[str] = None
    current_phase: Optional[int] = None
    intake_turn: Optional[int] = None
    intake_name: Optional[str] = None
    intake_grade: Optional[int] = None
    intake_stream: Optional[str] = None
    phase_2_category: Optional[str] = None
    personality: Optional[str] = None
    recommended_stream: Optional[str] = None
    report_available: bool = False


class CareerDirection(BaseModel):
    title: str
    confidence: int
    next_signal: str


class GrowthProfileResponse(BaseModel):
    is_ready: bool
    message: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)
    skills_possessed: list[str] = Field(default_factory=list)
    skills_to_develop: list[str] = Field(default_factory=list)
    growth_stage: str
    growth_stage_detail: Optional[str] = None
    activity_count: int = 0
    focus: Optional[str] = None
    career_directions: list[CareerDirection] = Field(default_factory=list)


class StudentOverviewResponse(BaseModel):
    user: MobileUser
    assessment: AssessmentStateResponse
    growth_profile: GrowthProfileResponse


class MonthlyPlanProgress(BaseModel):
    completed_weeks: int
    total_weeks: int
    percent: int
    completed_week_numbers: list[int] = Field(default_factory=list)
    current_week: Optional[int] = None


class MonthlyPlanResponse(BaseModel):
    status: Literal["not_created", "available"]
    month_key: str
    plan: Optional[dict[str, Any]] = None
    progress: Optional[MonthlyPlanProgress] = None


def serialize_mobile_user(user: models.User) -> dict[str, Any]:
    """Return only account fields needed by the signed-in mobile experience."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "onboarded": bool(user.onboarded),
    }


def serialize_assessment_state(assessment: Optional[models.AssessmentResult]) -> dict[str, Any]:
    """Return resumable assessment metadata, never raw answers or private notes."""
    if assessment is None:
        return {"status": "not_started"}

    is_complete = bool(
        assessment.assessment_report
        or assessment.phase3_result
        or assessment.recommended_stream
    )
    return {
        "status": "completed" if is_complete else "in_progress",
        "student_type": assessment.student_type,
        "current_phase": assessment.current_phase,
        "intake_turn": assessment.intake_turn,
        "intake_name": assessment.intake_name,
        "intake_grade": assessment.intake_grade,
        "intake_stream": assessment.intake_stream,
        "phase_2_category": assessment.phase_2_category,
        "personality": assessment.personality,
        "recommended_stream": assessment.recommended_stream,
        "report_available": bool(assessment.assessment_report),
    }


async def require_mobile_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> models.User:
    token = get_bearer_token(request.headers.get("authorization"))
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _get_active_user(
        token,
        db,
        invalid_token_detail="A valid bearer access token is required.",
    )


async def require_push_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> models.User:
    token = get_bearer_token(request.headers.get("authorization")) or request.cookies.get("user_id")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A signed-in CareStance account is required.",
        )
    return await _get_active_user(
        token,
        db,
        invalid_token_detail="The access token is invalid.",
    )


async def _get_active_user(
    token: str,
    db: AsyncSession,
    invalid_token_detail: str,
) -> models.User:
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_token_detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        numeric_user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        await db.execute(select(models.User).where(models.User.id == numeric_user_id))
    ).scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The account for this access token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_suspended:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is suspended.")
    return user


def build_auth_response(user: models.User) -> dict[str, Any]:
    return {
        "access_token": create_access_token(user.id, MOBILE_TOKEN_LIFETIME),
        "token_type": "bearer",
        "expires_in": int(MOBILE_TOKEN_LIFETIME.total_seconds()),
        "user": serialize_mobile_user(user),
    }


@router.post("/auth/login", response_model=AuthResponse)
async def mobile_login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip()
    user = (
        await db.execute(select(models.User).where(models.User.email == email))
    ).scalars().first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if user.is_suspended:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is suspended.")

    user.last_login = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return build_auth_response(user)


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def mobile_register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip()
    full_name = payload.full_name.strip()
    contact_number = payload.contact_number.strip()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
    if len(full_name) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter your full name.")
    if not PHONE_PATTERN.fullmatch(contact_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phone number must include a country code and a 10-digit number.",
        )
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password is required.")

    existing = (
        await db.execute(select(models.User).where(models.User.email == email))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists.")

    user = models.User(
        email=email,
        hashed_password=get_password_hash(payload.password),
        full_name=full_name,
        contact_number=contact_number,
        role=payload.role,
    )
    db.add(user)
    try:
        await db.flush()
        if payload.role == "counsellor":
            db.add(models.CounsellorProfile(user_id=user.id))
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists.")
    return build_auth_response(user)


@router.get("/me", response_model=MobileUser)
async def mobile_me(user: models.User = Depends(require_mobile_user)):
    return serialize_mobile_user(user)


def _is_supported_push_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    supported_hosts = (
        "fcm.googleapis.com",
        "push.services.mozilla.com",
        "push.apple.com",
        "notify.windows.com",
    )
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and bool(parsed.path)
        and any(host == domain or host.endswith("." + domain) for domain in supported_hosts)
    )


@router.get("/push/public-key")
async def push_public_key():
    public_key = get_vapid_public_key()
    return {"enabled": public_key is not None, "public_key": public_key}


@router.post("/push/subscriptions", status_code=status.HTTP_201_CREATED)
async def save_push_subscription(
    payload: PushSubscriptionRequest,
    user: models.User = Depends(require_push_user),
    db: AsyncSession = Depends(get_db),
):
    if not _is_supported_push_endpoint(payload.endpoint):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported push service endpoint.",
        )

    subscription = (
        await db.execute(
            select(models.PushSubscription).where(
                models.PushSubscription.endpoint == payload.endpoint
            )
        )
    ).scalars().first()
    if subscription is None:
        subscription = models.PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        db.add(subscription)
    else:
        subscription.user_id = user.id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth

    await db.commit()
    return {"subscribed": True}


@router.delete("/push/subscriptions")
async def delete_push_subscription(
    payload: PushSubscriptionRequest,
    user: models.User = Depends(require_push_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = (
        await db.execute(
            select(models.PushSubscription).where(
                models.PushSubscription.user_id == user.id,
                models.PushSubscription.endpoint == payload.endpoint,
            )
        )
    ).scalars().first()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()
    return {"subscribed": False}


@router.get("/student/overview", response_model=StudentOverviewResponse)
async def student_overview(
    user: models.User = Depends(require_mobile_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access is required.")
    assessment = (
        await db.execute(
            select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id)
        )
    ).scalars().first()
    return {
        "user": serialize_mobile_user(user),
        "assessment": serialize_assessment_state(assessment),
        "growth_profile": build_growth_profile(assessment),
    }


@router.get("/student/growth-profile", response_model=GrowthProfileResponse)
async def student_growth_profile(
    user: models.User = Depends(require_mobile_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access is required.")
    assessment = (
        await db.execute(
            select(models.AssessmentResult).where(models.AssessmentResult.user_id == user.id)
        )
    ).scalars().first()
    return build_growth_profile(assessment)


@router.get("/student/monthly-plan", response_model=MonthlyPlanResponse)
async def student_monthly_plan(
    user: models.User = Depends(require_mobile_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access is required.")
    month_key = datetime.date.today().strftime("%Y-%m")
    saved_plan = (
        await db.execute(
            select(models.MonthlyGrowthPlan).where(
                models.MonthlyGrowthPlan.user_id == user.id,
                models.MonthlyGrowthPlan.month_key == month_key,
            )
        )
    ).scalars().first()
    if saved_plan is None:
        return {"status": "not_created", "month_key": month_key, "plan": None}
    return {
        "status": "available",
        "month_key": saved_plan.month_key,
        "plan": saved_plan.plan_data,
        "progress": get_monthly_plan_progress(saved_plan.plan_data),
    }
