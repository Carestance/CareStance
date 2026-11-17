from types import SimpleNamespace

import pytest

from app.api.v1.mobile import serialize_assessment_state, serialize_mobile_user
from app.api.v1.mobile import require_mobile_user, student_overview
from fastapi import HTTPException
from app.security import create_access_token, get_bearer_token


def test_mobile_user_response_contains_only_safe_account_fields():
    user = SimpleNamespace(
        id=42,
        email="student@example.com",
        full_name="Student",
        role="student",
        onboarded=True,
        hashed_password="must-not-leak",
        contact_number="+911234567890",
    )

    response = serialize_mobile_user(user)

    assert response == {
        "id": 42,
        "email": "student@example.com",
        "full_name": "Student",
        "role": "student",
        "onboarded": True,
    }


def test_assessment_state_does_not_expose_answers_or_report_payload():
    assessment = SimpleNamespace(
        assessment_report={"private": "report payload"},
        phase3_result=None,
        recommended_stream="Science",
        student_type="12th",
        current_phase=6,
        intake_turn=3,
        intake_name="Student",
        intake_grade=12,
        intake_stream="Science",
        phase_2_category="Analytical",
        personality="Investigative",
        raw_answers={"sensitive": "answer"},
    )

    response = serialize_assessment_state(assessment)

    assert response["status"] == "completed"
    assert response["report_available"] is True
    assert "raw_answers" not in response
    assert "assessment_report" not in response


def test_missing_assessment_is_reported_as_not_started():
    assert serialize_assessment_state(None) == {"status": "not_started"}


def test_bearer_token_parser_rejects_other_auth_schemes_and_empty_tokens():
    assert get_bearer_token("Bearer signed-token") == "signed-token"
    assert get_bearer_token("bearer signed-token") == "signed-token"
    assert get_bearer_token("Basic credentials") is None
    assert get_bearer_token("Bearer ") is None


@pytest.mark.asyncio
async def test_student_overview_scopes_assessment_lookup_to_authenticated_user():
    class _Scalars:
        def first(self):
            return None

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Database:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return _Result()

    user = SimpleNamespace(id=73, role="student", email="student@example.com", full_name="Student", onboarded=True)
    db = _Database()

    result = await student_overview(user=user, db=db)

    assert db.statement.compile().params["user_id_1"] == 73
    assert result["assessment"] == {"status": "not_started"}


@pytest.mark.asyncio
async def test_student_overview_rejects_non_student_roles_before_querying():
    user = SimpleNamespace(id=73, role="teacher")

    with pytest.raises(HTTPException) as error:
        await student_overview(user=user, db=None)

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_mobile_auth_uses_the_signed_bearer_subject():
    user = SimpleNamespace(id=73, is_suspended=False)

    class _Scalars:
        def first(self):
            return user

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Database:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return _Result()

    db = _Database()
    request = SimpleNamespace(
        headers={"authorization": f"Bearer {create_access_token(73)}"}
    )

    authenticated_user = await require_mobile_user(request=request, db=db)

    assert authenticated_user is user
    assert db.statement.compile().params["id_1"] == 73


@pytest.mark.asyncio
async def test_mobile_auth_rejects_missing_bearer_token():
    with pytest.raises(HTTPException) as error:
        await require_mobile_user(
            request=SimpleNamespace(headers={"authorization": "Basic user:password"}),
            db=None,
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_application_lifespan_runs_registered_startup_and_shutdown(monkeypatch):
    from app import main

    events = []

    async def record_startup():
        events.append("startup")

    async def record_shutdown():
        events.append("shutdown")

    async def record_realtime_shutdown():
        events.append("realtime_shutdown")

    monkeypatch.setattr(main, "startup_event", record_startup)
    monkeypatch.setattr(main, "shutdown_event", record_shutdown)
    monkeypatch.setattr(main.session_manager, "shutdown_all", record_realtime_shutdown)

    async with main.lifespan(main.app):
        events.append("running")

    assert events == ["startup", "running", "shutdown", "realtime_shutdown"]
