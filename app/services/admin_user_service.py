"""
Admin User Service
Handles all DB queries for user management in the admin panel.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import selectinload

from app.models import User

logger = logging.getLogger(__name__)


async def get_all_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> dict:
    """
    Fetch paginated + optionally searched users.
    Returns: { users, total, page, page_size, total_pages }
    """
    query = select(User)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    # Total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginated users
    offset = (page - 1) * page_size
    query = query.order_by(User.id.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),  # ceiling division
    }


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def block_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Suspend/block a user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None

    user.is_suspended = True
    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin blocked user_id={user_id}")
    return user


async def unblock_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Reactivate a suspended user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None

    user.is_suspended = False
    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin unblocked user_id={user_id}")
    return user


async def reset_user_password(
    db: AsyncSession,
    user_id: int,
    new_hashed_password: str,
) -> Optional[User]:
    """
    Update a user's hashed password.
    Caller is responsible for hashing the new password before passing it here.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None

    user.hashed_password = new_hashed_password
    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin reset password for user_id={user_id}")
    return user