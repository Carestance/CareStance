import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock
from app.realtime.memory.repository import MemoryRepository
from app.realtime.memory.context_loader import ContextLoader

@pytest.mark.asyncio
async def test_get_summary_none():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result
    
    summary = await MemoryRepository.get_summary("client_123", mock_db)
    assert summary is None

@pytest.mark.asyncio
async def test_load_user_context_guest():
    mock_db = AsyncMock()
    context = await ContextLoader.load_user_context(None, mock_db)
    assert context["name"] == "Guest"
    assert context["grade"] == "Unknown"

@pytest.mark.asyncio
async def test_update_summary_creates_new():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result
    
    await MemoryRepository.update_summary("client_new", 1, "A new conversation summary.", mock_db)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
