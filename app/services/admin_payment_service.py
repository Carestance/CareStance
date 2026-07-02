"""
Admin Payment & Revenue Analytics Service
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models import Payment, SimulationPayment, Transfer, Appointment

logger = logging.getLogger(__name__)


async def get_payment_analytics(db: AsyncSession) -> dict:
    """
    Computes:
    - session_revenue     (captured payments only)
    - simulation_revenue  (all simulation payments)
    - total_revenue
    - counsellor_payouts  (processed transfers)
    - platform_commission
    - pending_payouts
    - failed_payouts
    """

    # 1. Session revenue — only captured payments
    session_rev_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == "captured"
        )
    )
    session_revenue = float(session_rev_result.scalar_one())

    # 2. Simulation revenue — successful payments
    sim_rev_result = await db.execute(
        select(func.coalesce(func.sum(SimulationPayment.amount), 0))
    )
    simulation_revenue = float(sim_rev_result.scalar_one())

    # 3. Counsellor payouts — processed transfers
    payouts_result = await db.execute(
        select(func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.status == "processed"
        )
    )
    counsellor_payouts = float(payouts_result.scalar_one())

    # 4. Pending payouts
    pending_result = await db.execute(
        select(func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.status == "pending"
        )
    )
    pending_payouts = float(pending_result.scalar_one())

    # 5. Failed payouts
    failed_result = await db.execute(
        select(func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.status == "failed"
        )
    )
    failed_payouts = float(failed_result.scalar_one())

    total_revenue = session_revenue + simulation_revenue
    platform_commission = (session_revenue - counsellor_payouts) + simulation_revenue

    return {
        "session_revenue": session_revenue,
        "simulation_revenue": simulation_revenue,
        "total_revenue": total_revenue,
        "counsellor_payouts": counsellor_payouts,
        "platform_commission": platform_commission,
        "pending_payouts": pending_payouts,
        "failed_payouts": failed_payouts,
    }


async def get_recent_payment_logs(db: AsyncSession, limit: int = 20) -> list:
    """Latest N payment records with session/appointment info."""
    result = await db.execute(
        select(Payment)
        .options(
            selectinload(Payment.session).selectinload(Appointment.student),
            selectinload(Payment.session).selectinload(Appointment.counsellor),
            selectinload(Payment.transfers),
        )
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()