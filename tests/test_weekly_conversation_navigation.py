import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.main import templates
from app import main


def _request(path):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        state=SimpleNamespace(growth_map_url=None),
    )


def test_weekly_conversation_link_keeps_selected_career():
    week = {
        "week": 1,
        "title": "Build a project",
        "goal": "Practice analysis",
        "outcome": "Complete a portfolio project",
        "tasks": [],
    }
    html = templates.get_template("monthly_week.html").render({
        "request": _request("/my-monthly-path/week/1"),
        "user": SimpleNamespace(role="student", id=1),
        "plan": {
            "career_title": "Data Science",
            "focus_skill": "analysis",
            "weeks": [week],
        },
        "career": "Data Science",
        "week": week,
        "progress": {
            "percent": 25,
            "completed_week_numbers": [],
            "current_week": 1,
            "completed_weeks": 0,
            "total_weeks": 4,
        },
        "task_states": [],
        "cycle": {
            "weekly_conversation_due": True,
            "weekend_quiz_due": False,
            "latest_quiz": None,
        },
        "weekend_quiz": [],
    })

    assert 'href="/my-monthly-path/week/1/conversation?career=Data%20Science"' in html


def test_weekly_conversation_back_link_keeps_selected_career():
    html = templates.get_template("monthly_conversation.html").render({
        "request": _request("/my-monthly-path/week/1/conversation"),
        "user": SimpleNamespace(role="student", id=1),
        "career": "Data Science",
        "week_number": 1,
        "conversation": {
            "messages": [{"role": "assistant", "content": "Welcome."}],
        },
        "remaining_seconds": 240,
        "minimum_remaining_seconds": 180,
    })

    assert 'href="/my-monthly-path/week/1?career=Data%20Science"' in html
    assert 'const careerQuery = "?career=Data%20Science"' in html


@pytest.mark.asyncio
async def test_admin_can_complete_weekly_conversation_from_week_workspace(monkeypatch):
    user = SimpleNamespace(id=1, role="admin")
    started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=190)
    conversation = {
        "week": 1,
        "started_at": started_at.isoformat(),
        "messages": [{"role": "assistant", "content": "Welcome."}],
    }
    plan_record = SimpleNamespace(plan_data={"weekly_conversations": [conversation], "weeks": []})
    db = SimpleNamespace(commit=AsyncMock())
    request = SimpleNamespace(
        query_params={},
        json=AsyncMock(return_value={"message": "I made progress."}),
    )
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "_get_current_monthly_plan_record", AsyncMock(return_value=plan_record))
    monkeypatch.setattr(main.templates, "TemplateResponse", lambda **_kwargs: "conversation page")
    monkeypatch.setattr(main, "generate_content_with_fallback", AsyncMock(return_value="What will you try next?"))

    page = await main.weekly_growth_conversation(1, request, db)
    reply = await main.weekly_growth_conversation_message(1, request, db)
    completion = await main.complete_weekly_growth_conversation(1, request, db)

    assert page == "conversation page"
    assert reply["response"] == "What will you try next?"
    assert completion == {"redirect": "/my-monthly-path/week/1"}
    assert conversation["completed_at"]
    assert db.commit.await_count == 2
