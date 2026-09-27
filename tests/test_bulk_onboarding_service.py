import io
import openpyxl
import pytest

from app.services.bulk_onboarding_service import (
    build_credentials_workbook,
    generate_secure_password,
    get_bulk_onboarding_plan_assignment,
    parse_bulk_onboarding_records,
    build_bulk_onboarding_report,
    bulk_onboard_users,
)
from app.security import get_password_hash, verify_password, pwd_context


def test_build_credentials_workbook_returns_xlsx_with_account_credentials():
    workbook_bytes = build_credentials_workbook({
        "created": [{
            "full_name": "Student One",
            "email": "student1@example.com",
            "password": "Secure123!",
            "role": "student",
            "user_id": 42,
        }],
        "summary": {"created_count": 1, "skipped_count": 0, "failure_count": 0},
    })

    assert workbook_bytes[:2] == b"PK"
    wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes))
    assert "Account Credentials" in wb.sheetnames


def test_parse_bulk_onboarding_records_accepts_json_and_csv_inputs():
    json_records = parse_bulk_onboarding_records(
        '[{"email": "student1@example.com", "full_name": "Student One", "contact_number": "+91 90000 00001", "role": "student"}]'
    )
    csv_records = parse_bulk_onboarding_records(
        'email,full_name,contact_number,role\nstudent2@example.com,Student Two,+91 90000 00002,student'
    )

    assert len(json_records) == 1
    assert json_records[0]["email"] == "student1@example.com"
    assert len(csv_records) == 1
    assert csv_records[0]["email"] == "student2@example.com"


def test_build_bulk_onboarding_report_returns_clear_summary_view():
    result = {
        "created": [{"email": "a@example.com"}],
        "skipped": [{"email": "b@example.com", "reason": "duplicate_user"}],
        "failures": [{"email": "c@example.com", "reason": "invalid_email"}],
    }

    report = build_bulk_onboarding_report(result)

    assert report["created_count"] == 1
    assert report["skipped_count"] == 1
    assert report["failure_count"] == 1
    assert report["created_emails"] == ["a@example.com"]
    assert report["duplicate_emails"] == ["b@example.com"]
    assert report["failure_emails"] == ["c@example.com"]


def test_generate_secure_password_is_secure_and_reasonable():
    password = generate_secure_password(16)

    assert len(password) >= 12
    assert any(char.isupper() for char in password)
    assert any(char.isdigit() for char in password)
    assert any(char in "!@#$%^&*" for char in password)


def test_bulk_onboarding_plan_assignment_marks_active_paid_access_for_r300_service_bundle():
    assignment = get_bulk_onboarding_plan_assignment()

    assert assignment["plan"] == "customised"
    assert assignment["status"] == "active"
    assert assignment["expires_at_days"] == 3650
    assert assignment["services"] == [
        "live_talk",
        "growth_map",
        "simulations",
        "weekly_talks",
        "r300_bundle",
    ]


def test_admin_router_registers_bulk_onboarding_admin_route():
    from app.routes.admin import router

    route_paths = {route.path for route in router.routes}
    assert "/admin/bulk-onboard" in route_paths


def test_build_onboarding_milestone_payload_returns_day_3_milestone_tasks_and_progress():
    from app.services.onboarding_milestone_service import build_onboarding_milestone_payload

    payload = build_onboarding_milestone_payload(
        completed_tasks=["profile_setup", "upi_setup"],
        user_name="Aarav",
    )

    assert payload["day"] == 3
    assert payload["user_name"] == "Aarav"
    assert payload["total_tasks"] == 3
    assert payload["completed_tasks"] == ["profile_setup", "upi_setup"]
    assert payload["progress_percent"] == 67
    assert [task["id"] for task in payload["tasks"]] == [
        "profile_setup",
        "upi_setup",
        "verification_review",
    ]


def test_password_hashing_and_verification_bcrypt_no_72_byte_error():
    # Normal password
    pwd = generate_secure_password(16)
    hashed = get_password_hash(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

    # pwd_context compatibility
    ctx_hash = pwd_context.hash(pwd)
    assert pwd_context.verify(pwd, ctx_hash) is True

    # Passwords longer than 72 bytes must never raise ValueError
    long_pwd = "A" * 150 + "!@#"
    long_hash = get_password_hash(long_pwd)
    assert verify_password(long_pwd, long_hash) is True
    assert pwd_context.verify(long_pwd, pwd_context.hash(long_pwd)) is True


@pytest.mark.asyncio
async def test_bulk_onboard_users_creates_accounts_without_bcrypt_byte_limit_error():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.models import Base, User

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        records = [
            {"email": "student1@example.com", "full_name": "Student One", "role": "student"},
            {"email": "student2@example.com", "full_name": "Student Two", "role": "student"},
        ]
        result = await bulk_onboard_users(session, records)
        assert len(result["created"]) == 2
        assert result["summary"]["created_count"] == 2

        user_entry = result["created"][0]
        plain_pw = user_entry["password"]

        res = await session.execute(select(User).where(User.email == "student1@example.com"))
        db_user = res.scalar_one()
        assert verify_password(plain_pw, db_user.hashed_password) is True

    await engine.dispose()

