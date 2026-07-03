import asyncio
import datetime as dt
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT_DIR)
sys.path.append(ROOT_DIR)

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models import (
    Appointment,
    AssessmentResult,
    CounsellorProfile,
    ModerationFlag,
    Payment,
    SimulationPayment,
    Transfer,
    User,
)
from app.services.admin_analytics_service import get_moderation_flags, get_recent_appointments
from app.services.admin_payment_service import get_payment_analytics


STUDENT_EMAIL = "smoke.student@carestance.test"
COUNSELLOR_EMAIL = "smoke.counsellor@carestance.test"


async def ensure_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(db, email, full_name, role):
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user:
        user.full_name = full_name
        user.role = role
        user.is_suspended = False
        return user

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        hashed_password="smoke-test-password-placeholder",
        is_suspended=False,
    )
    db.add(user)
    await db.flush()
    return user


async def upsert_payment(db, session_id, order_id, amount, status):
    payment = (
        await db.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
    ).scalar_one_or_none()
    if not payment:
        payment = Payment(razorpay_order_id=order_id)
        db.add(payment)
        await db.flush()

    payment.session_id = session_id
    payment.amount = amount
    payment.currency = "INR"
    payment.status = status
    payment.razorpay_payment_id = f"{order_id}_pay" if status == "captured" else None
    return payment


async def upsert_sim_payment(db, user_id, order_id, amount, status):
    sim_payment = (
        await db.execute(
            select(SimulationPayment).where(SimulationPayment.razorpay_order_id == order_id)
        )
    ).scalar_one_or_none()
    if not sim_payment:
        sim_payment = SimulationPayment(razorpay_order_id=order_id)
        db.add(sim_payment)

    sim_payment.user_id = user_id
    sim_payment.amount = amount
    sim_payment.status = status
    sim_payment.career = "Urban and Regional Planners"
    sim_payment.razorpay_payment_id = f"{order_id}_pay" if status in {"success", "captured"} else None
    return sim_payment


async def seed():
    await ensure_schema()
    async with AsyncSessionLocal() as db:
        student = await get_or_create_user(
            db, STUDENT_EMAIL, "Smoke Test Student", "student"
        )
        counsellor = await get_or_create_user(
            db, COUNSELLOR_EMAIL, "Smoke Test Counsellor", "counsellor"
        )
        await db.flush()

        profile = (
            await db.execute(
                select(CounsellorProfile).where(CounsellorProfile.user_id == counsellor.id)
            )
        ).scalar_one_or_none()
        if not profile:
            profile = CounsellorProfile(user_id=counsellor.id)
            db.add(profile)
        profile.fee = 500
        profile.is_verified = True
        profile.verification_status = "approved"
        profile.verification_remarks = "Smoke test verified counsellor"

        appointment = (
            await db.execute(
                select(Appointment).where(
                    Appointment.student_id == student.id,
                    Appointment.counsellor_id == counsellor.id,
                    Appointment.meeting_link == "https://meet.example.com/carestance-smoke",
                )
            )
        ).scalar_one_or_none()
        if not appointment:
            appointment = Appointment(
                student_id=student.id,
                counsellor_id=counsellor.id,
                meeting_link="https://meet.example.com/carestance-smoke",
            )
            db.add(appointment)
            await db.flush()

        appointment.appointment_time = dt.datetime.now() + dt.timedelta(days=1)
        appointment.status = "accepted"
        appointment.payment_status = "paid"

        captured = await upsert_payment(
            db, appointment.id, "order_smoke_captured", 500, "captured"
        )
        await upsert_payment(db, appointment.id, "order_smoke_failed", 999, "failed")
        await upsert_payment(db, appointment.id, "order_smoke_created", 777, "created")
        await db.flush()

        transfer = (
            await db.execute(select(Transfer).where(Transfer.payment_id == captured.id))
        ).scalar_one_or_none()
        if not transfer:
            transfer = Transfer(payment_id=captured.id, counsellor_id=counsellor.id)
            db.add(transfer)
        transfer.amount = 350
        transfer.status = "processed"
        transfer.razorpay_transfer_id = "trf_smoke_processed"

        await upsert_sim_payment(db, student.id, "sim_smoke_success", 10, "success")
        await upsert_sim_payment(db, student.id, "sim_smoke_failed", 20, "failed")

        flag = (
            await db.execute(
                select(ModerationFlag).where(
                    ModerationFlag.user_id == student.id,
                    ModerationFlag.content == "Smoke moderation flag content",
                )
            )
        ).scalar_one_or_none()
        if not flag:
            flag = ModerationFlag(
                user_id=student.id,
                content="Smoke moderation flag content",
                chat_type="ai",
            )
            db.add(flag)
        flag.status = "pending_review"
        flag.flag_type = "smoke_test"
        flag.severity = "medium"
        flag.admin_note = None

        assessment = (
            await db.execute(
                select(AssessmentResult).where(AssessmentResult.user_id == student.id)
            )
        ).scalar_one_or_none()
        if not assessment:
            assessment = AssessmentResult(user_id=student.id)
            db.add(assessment)
        assessment.student_type = "10th"
        assessment.selected_class = "10th"
        assessment.current_phase = 5
        assessment.personality = "Artistic"
        assessment.recommended_stream = "Humanities"
        assessment.assessment_report = {
            "pipeline_version": "v2_vector_real_data",
            "final_recommendations": [
                {
                    "career": "Urban and Regional Planners",
                    "confidence_score": 0.98,
                    "feasibility_status": "Optimal Fit",
                    "pivot_notes": "Smoke test top match.",
                },
                {
                    "career": "Landscape Architects",
                    "confidence_score": 0.97,
                    "feasibility_status": "Optimal Fit",
                    "pivot_notes": "Smoke test second match.",
                },
                {
                    "career": "Architectural and Engineering Managers",
                    "confidence_score": 0.96,
                    "feasibility_status": "Optimal Fit",
                    "pivot_notes": "Smoke test third match.",
                },
            ],
        }

        await db.commit()
        print("Seeded smoke data")
        print(f"Student: {student.email}")
        print(f"Counsellor: {counsellor.email}")


async def verify():
    await ensure_schema()
    async with AsyncSessionLocal() as db:
        appointments = await get_recent_appointments(db)
        analytics = await get_payment_analytics(db)
        flags = await get_moderation_flags(db)

        smoke_appointments = [
            a
            for a in appointments
            if a.meeting_link == "https://meet.example.com/carestance-smoke"
        ]
        smoke_flags = [f for f in flags if f.content == "Smoke moderation flag content"]

        print(f"Smoke appointments visible to admin: {len(smoke_appointments)}")
        if smoke_appointments:
            appt = smoke_appointments[0]
            print(f"Student loaded: {appt.student.full_name} <{appt.student.email}>")
            print(f"Counsellor loaded: {appt.counsellor.full_name} <{appt.counsellor.email}>")
            print(f"Appointment status: {appt.status}")
            print(f"Payment status: {appt.payment_status}")
            print(f"Meeting link: {appt.meeting_link}")

        print(f"Session revenue includes captured only: {analytics['session_revenue']}")
        print(f"Simulation revenue includes success/captured only: {analytics['simulation_revenue']}")
        print(f"Counsellor payouts include processed only: {analytics['counsellor_payouts']}")
        print(f"Platform commission: {analytics['platform_commission']}")
        print(f"Smoke moderation flags visible to admin: {len(smoke_flags)}")


async def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if action == "seed":
        await seed()
    elif action == "verify":
        await verify()
    else:
        raise SystemExit("Usage: python scripts/seed_admin_smoke_data.py [seed|verify]")


if __name__ == "__main__":
    asyncio.run(main())
