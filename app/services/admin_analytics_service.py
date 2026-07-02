"""
Admin Analytics Service
Handles appointments listing and moderation flag management.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Appointment, ModerationFlag, User

logger = logging.getLogger(__name__)


# ── Appointments ──────────────────────────────────────────────────────────────

async def get_recent_appointments(db: AsyncSession, limit: int = 50) -> list:
    """
    Latest N appointments with student + counsellor loaded eagerly.
    joinedload used to prevent async lazy-loading / greenlet_spawn errors.
    """
    result = await db.execute(
        select(Appointment)
        .options(
            joinedload(Appointment.student),
            joinedload(Appointment.counsellor),
        )
        .order_by(Appointment.appointment_time.desc())
        .limit(limit)
    )
    return result.unique().scalars().all()


# ── Moderation Flags ──────────────────────────────────────────────────────────

async def get_moderation_flags(db: AsyncSession, limit: int = 50) -> list:
    """Latest N moderation flags with user info."""
    result = await db.execute(
        select(ModerationFlag)
        .options(selectinload(ModerationFlag.user))
        .order_by(ModerationFlag.timestamp.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def resolve_moderation_flag(
    db: AsyncSession,
    flag_id: int,
    new_status: str,
    admin_note: str = None,
) -> Optional[ModerationFlag]:
    """
    Update a moderation flag's status.
    Valid: pending_review, dismissed, action_taken
    """
    VALID = {"pending_review", "dismissed", "action_taken"}
    if new_status not in VALID:
        raise ValueError(f"Invalid status. Must be one of: {VALID}")

    result = await db.execute(
        select(ModerationFlag).where(ModerationFlag.id == flag_id)
    )
    flag = result.scalar_one_or_none()
    if not flag:
        return None

    flag.status = new_status
    # Store admin note in content field temporarily until column is added
    # TODO: add admin_note column to ModerationFlag model
    if admin_note:
        logger.info(f"Admin note for flag {flag_id}: {admin_note}")

    await db.commit()
    await db.refresh(flag)
    logger.info(f"Moderation flag {flag_id} updated to '{new_status}'")
    return flag