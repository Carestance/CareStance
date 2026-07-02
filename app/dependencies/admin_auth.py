"""
Admin authentication dependency
Reusable across all admin-only routes and APIs.
"""

import os
import logging
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db  # adjust import path as per your project
from app.models import User

logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: validates session cookie and checks admin role.
    Use this in any admin-only route.

    Raises:
        RedirectResponse → /login  (no session)
        HTTPException 403         (logged in but not admin)
    """
    user_id = request.cookies.get("user_id")

    try:
        uid = int(user_id)
    except ValueError:
        return RedirectResponse(url="/login", status_code=302)

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        return RedirectResponse(url="/login", status_code=302)

    is_admin = (user.role == "admin") or (user.email == ADMIN_EMAIL)

    if not is_admin:
        logger.warning(
            f"Unauthorized admin access attempt by user_id={user_id} email={user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access denied.",
        )

    return user