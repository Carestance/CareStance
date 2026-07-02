"""
Admin Counsellor Service
Handles verification queue, approval/rejection, block/unblock, analytics.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import selectinload, joinedload

from app.models import CounsellorProfile, Appointment, User

logger = logging.getLogger(__name__)


async def get_pending_counsellors(db: AsyncSession) -> list:
    """Fetch all counsellors with verification_status = 'pending'."""
    result = await db.execute(
        select(CounsellorProfile)
        .options(selectinload(CounsellorProfile.user))
        .where(CounsellorProfile.verification_status == "pending")
        .order_by(CounsellorProfile.id.asc())
    )
    return result.scalars().all()


async def get_all_counsellors(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> dict:
    """Paginated counsellor list with optional name/email search."""
    query = (
        select(CounsellorProfile)
        .options(selectinload(CounsellorProfile.user))
        .join(User, CounsellorProfile.user_id == User.id)
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.ilike(term),
                User.email.ilike(term),
            )
        )

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(CounsellorProfile.id.desc()).offset(offset).limit(page_size)
    )
    counsellors = result.scalars().all()

    return {
        "counsellors": counsellors,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def approve_counsellor(
    db: AsyncSession, profile_id: int, remarks: str = None
) -> Optional[CounsellorProfile]:
    result = await db.execute(
        select(CounsellorProfile).where(CounsellorProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None

    profile.verification_status = "approved"
    profile.is_verified = True
    if remarks:
        profile.block_reason = remarks  # reusing field; rename to remarks if you add column
    await db.commit()
    await db.refresh(profile)
    logger.info(f"Counsellor profile {profile_id} approved")
    return profile


async def reject_counsellor(
    db: AsyncSession, profile_id: int, remarks: str = None
) -> Optional[CounsellorProfile]:
    result = await db.execute(
        select(CounsellorProfile).where(CounsellorProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None

    profile.verification_status = "rejected"
    profile.is_verified = False
    if remarks:
        profile.block_reason = remarks
    await db.commit()
    await db.refresh(profile)
    logger.info(f"Counsellor profile {profile_id} rejected. Remarks: {remarks}")
    return profile


async def block_counsellor(
    db: AsyncSession, profile_id: int, reason: str = None
) -> Optional[CounsellorProfile]:
    result = await db.execute(
        select(CounsellorProfile).where(CounsellorProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None

    profile.is_blocked = True
    if reason:
        profile.block_reason = reason
    await db.commit()
    await db.refresh(profile)
    logger.info(f"Counsellor profile {profile_id} blocked")
    return profile


async def unblock_counsellor(
    db: AsyncSession, profile_id: int
) -> Optional[CounsellorProfile]:
    result = await db.execute(
        select(CounsellorProfile).where(CounsellorProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None

    profile.is_blocked = False
    profile.block_reason = None
    await db.commit()
    await db.refresh(profile)
    logger.info(f"Counsellor profile {profile_id} unblocked")
    return profile


async def get_counsellor_session_analytics(db: AsyncSession) -> list:
    """
    Grouped SQL aggregation — counts sessions by status per counsellor.
    No Python-side looping over appointments.
    """
    result = await db.execute(
        select(
            Appointment.counsellor_id,
            func.count(Appointment.id).label("total"),
            func.sum(
                case((Appointment.status == "completed", 1), else_=0)
            ).label("completed"),
            func.sum(
                case((Appointment.status == "cancelled", 1), else_=0)
            ).label("cancelled"),
            func.sum(
                case(
                    (
                        Appointment.status.in_(["accepted", "requested"]),
                        1,
                    ),
                    else_=0,
                )
            ).label("upcoming"),
        ).group_by(Appointment.counsellor_id)
    )
    rows = result.all()

    # Return as list of dicts for easy Jinja2 consumption
    return [
        {
            "counsellor_id": row.counsellor_id,
            "total": row.total,
            "completed": row.completed,
            "cancelled": row.cancelled,
            "upcoming": row.upcoming,
        }
        for row in rows
    ]