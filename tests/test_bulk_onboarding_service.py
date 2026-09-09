from app.services.bulk_onboarding_service import (
    generate_secure_password,
    get_bulk_onboarding_plan_assignment,
)


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
