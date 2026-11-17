from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import main


@pytest.mark.asyncio
async def test_admin_free_preview_advances_stale_locked_assessment_phase(monkeypatch):
    user = SimpleNamespace(id=1, role="admin")
    assessment = SimpleNamespace(current_phase=6)
    query_result = MagicMock()
    query_result.scalars.return_value.first.return_value = assessment
    db = SimpleNamespace(
        execute=AsyncMock(return_value=query_result),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(main, "get_current_user", AsyncMock(return_value=user))
    monkeypatch.setattr(main, "has_assessment_all_access", lambda _: True)

    response = await main.assessment_free_preview(None, db)

    assert response.status_code == 302
    assert response.headers["location"] == "/assessment"
    assert assessment.current_phase == 3
    db.commit.assert_awaited_once()
