from app.services.bulk_onboarding_service import (
    generate_secure_password,
    get_bulk_onboarding_plan_assignment,
    parse_bulk_onboarding_records,
    build_bulk_onboarding_report,
)


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
