"""
Admin Feedback & Support Ticket Service
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models import Feedback, Ticket

logger = logging.getLogger(__name__)


async def get_feedback_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated feedback logs, newest first."""
    count_result = await db.execute(select(func.count(Feedback.id)))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Feedback)
        .options(selectinload(Feedback.user))
        .order_by(Feedback.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )
    feedbacks = result.scalars().all()

    return {
        "feedback_logs": feedbacks,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def get_support_tickets(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str = None,
) -> dict:
    """Paginated support tickets with optional status filter."""
    query = select(Ticket).options(selectinload(Ticket.user))

    if status_filter:
        query = query.where(Ticket.status == status_filter)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Ticket.timestamp.desc()).offset(offset).limit(page_size)
    )
    tickets = result.scalars().all()

    return {
        "support_tickets": tickets,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def update_ticket_status(
    db: AsyncSession,
    ticket_id: int,
    new_status: str,
    admin_reply: str = None,
) -> Ticket | None:
    """
    Update ticket status. Valid statuses: Open, In Progress, Resolved, Closed
    """
    VALID_STATUSES = {"Open", "In Progress", "Resolved", "Closed"}
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status. Must be one of: {VALID_STATUSES}")

    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()

    if not ticket:
        return None

    ticket.status = new_status
    if admin_reply is not None:
        ticket.admin_reply = admin_reply

    await db.commit()
    await db.refresh(ticket)
    logger.info(f"Ticket {ticket_id} status updated to '{new_status}'")
    return ticket