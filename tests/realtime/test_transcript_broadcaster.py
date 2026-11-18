from types import SimpleNamespace

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from app.realtime.pipecat.broadcaster import TranscriptBroadcaster


@pytest.mark.asyncio
async def test_final_transcript_is_broadcast_and_forwarded():
    broadcaster = TranscriptBroadcaster(
        SimpleNamespace(is_closing=False),
        broadcast_assistant=False,
    )
    sent_frames = []

    async def record_frame(frame, direction):
        sent_frames.append((frame, direction))

    broadcaster.push_frame = record_frame
    transcript = TranscriptionFrame(
        text="I enjoy biology",
        user_id="student-1",
        timestamp="2025-01-01T00:00:00Z",
        finalized=True,
    )

    await broadcaster.process_frame(transcript, FrameDirection.DOWNSTREAM)

    assert len(sent_frames) == 2
    broadcast, direction = sent_frames[0]
    assert broadcast.message == {
        "type": "TRANSCRIPT_FINAL",
        "role": "user",
        "text": "I enjoy biology",
    }
    assert direction == FrameDirection.DOWNSTREAM
    assert sent_frames[1] == (transcript, FrameDirection.DOWNSTREAM)


@pytest.mark.asyncio
async def test_unfinalized_transcript_is_marked_partial():
    broadcaster = TranscriptBroadcaster(
        SimpleNamespace(is_closing=False),
        broadcast_assistant=False,
    )
    sent_frames = []

    async def record_frame(frame, direction):
        sent_frames.append(frame)

    broadcaster.push_frame = record_frame
    transcript = TranscriptionFrame(
        text="I enjoy",
        user_id="student-1",
        timestamp="2025-01-01T00:00:00Z",
        finalized=False,
    )

    await broadcaster.process_frame(transcript, FrameDirection.DOWNSTREAM)

    assert sent_frames[0].message["type"] == "TRANSCRIPT_PARTIAL"
    assert sent_frames[-1] is transcript
