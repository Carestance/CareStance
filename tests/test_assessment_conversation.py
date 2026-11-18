import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import main


class _QueryResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Database:
    def __init__(self, value):
        self.value = value
        self.commits = 0

    async def execute(self, _statement):
        return _QueryResult(self.value)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_chat_mode_routes_to_assessment_conversation(monkeypatch):
    user = SimpleNamespace(id=7)
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "has_assessment_all_access", lambda _: True)

    response = await main.assessment_phase3(None, mode="chat", db=None)

    assert response.status_code == 302
    assert response.headers["location"] == "/chatbot?mode=assessment"


@pytest.mark.asyncio
async def test_assessment_chatbot_loads_assessment_history(monkeypatch):
    user = SimpleNamespace(id=7)
    assessment = SimpleNamespace(
        chat_messages=[
            {"role": "user", "content": "I enjoy biology."},
            {"role": "assistant", "content": "What topics interest you?"},
        ]
    )
    db = _Database(assessment)
    rendered = {}
    template = SimpleNamespace(
        render=lambda context: rendered.update(context) or "assessment chat"
    )
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "has_assessment_all_access", lambda _: True)
    monkeypatch.setattr(main.templates, "get_template", lambda _name: template)

    response = await main.chatbot_page(None, mode="assessment", db=db)

    assert response.body == b"assessment chat"
    assert rendered["is_assessment_mode"] is True
    assert rendered["assessment_history"] == assessment.chat_messages
    assert [message["sender"] for message in rendered["history"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_assessment_chat_persists_context_and_ai_response(monkeypatch):
    user = SimpleNamespace(id=7)
    assessment = SimpleNamespace(
        raw_answers={
            "name": "Ari",
            "interests": ["design", "biology"],
        },
        student_type="Undergraduate",
        phase_2_category="Investigative",
        chat_messages=[],
    )
    db = _Database(assessment)
    submitted_messages = {}

    async def create_completion(**kwargs):
        submitted_messages.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Tell me more."))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_completion)
        )
    )
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "has_assessment_all_access", lambda _: True)
    monkeypatch.setattr(main, "get_groq_client", lambda: client)

    response = await main.phase3_chat_v2(
        None,
        main.Phase3V2ChatRequest(
            message="I enjoy biology.",
            answers=[{"role": "user", "content": "I enjoy biology."}],
        ),
        db,
    )

    assert json.loads(response.body)["response"] == "Tell me more."
    assert len(assessment.chat_messages) == 2
    assert assessment.chat_messages[0] == {
        "role": "user",
        "content": "I enjoy biology.",
    }
    assert assessment.chat_messages[1]["role"] == "assistant"
    system_prompt = submitted_messages["messages"][0]["content"]
    assert "Ari" in system_prompt
    assert "design, biology" in system_prompt
    assert db.commits == 2


@pytest.mark.asyncio
async def test_assessment_chat_saves_user_message_and_returns_error_without_provider(monkeypatch):
    user = SimpleNamespace(id=7)
    assessment = SimpleNamespace(
        raw_answers={},
        student_type="Unknown",
        phase_2_category="Unknown",
        chat_messages=[],
    )
    db = _Database(assessment)
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "has_assessment_all_access", lambda _: True)
    monkeypatch.setattr(main, "get_groq_client", lambda: None)
    monkeypatch.setattr(main, "GEMINI_API_KEY", None)

    with pytest.raises(HTTPException) as error:
        await main.phase3_chat_v2(
            None,
            main.Phase3V2ChatRequest(message="I enjoy biology."),
            db,
        )

    assert error.value.status_code == 503
    assert assessment.chat_messages == [
        {"role": "user", "content": "I enjoy biology."}
    ]
    assert db.commits == 1
