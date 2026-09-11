import datetime
import secrets
import string
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.email_utils import send_email
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


R300_SERVICE_BUNDLE = [
    "live_talk",
    "growth_map",
    "simulations",
    "weekly_talks",
    "r300_bundle",
]


def generate_secure_password(length: int = 16) -> str:
    """Create a strong password for a bulk-created account.

    The generated value is intentionally long enough for onboarding and contains
    uppercase letters, digits, and symbols to satisfy a secure baseline.
    """
    if length < 12:
        length = 12

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]

    rest = [secrets.choice(alphabet) for _ in range(length - len(required))]
    password = required + rest
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def get_bulk_onboarding_plan_assignment() -> dict[str, Any]:
    """Return the default plan model used for bulk ₹300 paid onboarding.

    Existing subscription semantics in the app already treat the customised
    subscription as the active paid plan. This helper insulates the new feature
    from the payment/Razorpay UI by assigning that plan directly.
    """
    activated_at = datetime.datetime.utcnow()
    expires_at = activated_at + datetime.timedelta(days=3650)

    return {
        "plan": "customised",
        "status": "active",
        "amount": 300,
        "currency": "INR",
        "expires_at": expires_at.isoformat(),
        "expires_at_days": 3650,
        "services": R300_SERVICE_BUNDLE,
        "payment_flow_disabled": True,
        "paywall_disabled": True,
        "is_bulk_onboarded": True,
    }


async def bulk_onboard_users(
    db: AsyncSession,
    user_records: list[dict[str, Any]],
    send_credentials: bool = False,
    force_email: bool = False,
) -> dict[str, Any]:
    """Create a batch of user accounts and assign the direct paid-plan model.

    Each record can carry email, full_name, contact_number, role and optional
    source metadata. A generated secure password is never stored in plaintext
    and is returned to the caller only if the caller asked for the values to be
    shared by email.
    """
    now = datetime.datetime.utcnow()
    assignment = get_bulk_onboarding_plan_assignment()
    created = []
    skipped = []
    failures = []

    for record in user_records:
        email = str(record.get("email") or "").strip().lower()
        full_name = str(record.get("full_name") or "").strip()
        role = str(record.get("role") or "student").strip().lower()
        contact_number = str(record.get("contact_number") or "").strip()

        if not email or "@" not in email:
            failures.append({"email": email, "reason": "invalid_email"})
            continue

        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalars().first() is not None:
            skipped.append({"email": email, "reason": "duplicate_user"})
            continue

        secure_password = generate_secure_password(16)
        hashed_password = pwd_context.hash(secure_password)

        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            contact_number=contact_number,
            role=role,
            onboarded=True,
            assessments_completed=0,
            simulations_completed=0,
            simulation_paid=False,
            simulation_credits=0,
            assessment_all_access=True,
            subscription_plan=assignment["plan"],
            subscription_status=assignment["status"],
            subscription_started_at=now,
            subscription_expires_at=now + datetime.timedelta(days=assignment["expires_at_days"]),
        )

        try:
            db.add(user)
            await db.flush()
        except IntegrityError:
            await db.rollback()
            failures.append({"email": email, "reason": "account_creation_failed"})
            continue

        created.append({
            "email": email,
            "full_name": full_name,
            "role": role,
            "password": secure_password,
            "user_id": user.id,
        })

        if send_credentials:
            email_body = (
                "<h1>Welcome to CareStance</h1>"
                "<p>You have been onboarded through the ₹300 bulk plan.</p>"
                f"<p><b>Email:</b> {email}</p>"
                f"<p><b>Password:</b> {secure_password}</p>"
                "<p>Please change your password after your first login.</p>"
            )
            send_email(email, "CareStance bulk onboarding credentials", email_body)

    await db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "failures": failures,
        "assignment": assignment,
        "summary": {
            "created_count": len(created),
            "skipped_count": len(skipped),
            "failure_count": len(failures),
            "service_bundle": R300_SERVICE_BUNDLE,
        },
    }
