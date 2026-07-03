"""Reusable admin authentication dependency."""

import logging
import os

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the user_id cookie and allow only admins or ADMIN_EMAIL."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
            detail="Login required.",
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
            detail="Invalid session.",
        )

    result = await db.execute(select(User).where(User.id == user_id_int))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
            detail="Login required.",
        )

    # Deny suspended/blocked users (module requirement)
    if getattr(user, "is_suspended", False):
        logger.warning("Suspended user blocked from admin access: user_id=%s email=%s", user.id, user.email)
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/suspended"},
            detail="Account suspended.",
        )

    admin_email = os.getenv("ADMIN_EMAIL", "")
    is_admin = user.role == "admin" or (bool(admin_email) and user.email == admin_email)
    if not is_admin:
        logger.warning(
            "Unauthorized admin access attempt by user_id=%s email=%s",
            user.id,
            user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/dashboard?error=Admin+access+denied"},
            detail="Admin access denied.",
        )

    return user
