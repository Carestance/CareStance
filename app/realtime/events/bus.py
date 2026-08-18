from enum import Enum, auto
from typing import Any, Callable, Dict
import asyncio
from dataclasses import dataclass, field

class EventType(Enum):
    SESSION_CREATED = auto()
    SESSION_READY = auto()
    CLIENT_CONNECTED = auto()
    CLIENT_DISCONNECTED = auto()
    USER_SPEECH_STARTED = auto()
    USER_SPEECH_STOPPED = auto()
    TRANSCRIPT_PARTIAL = auto()
    TRANSCRIPT_FINAL = auto()
    LLM_REQUEST_STARTED = auto()
    LLM_FIRST_TOKEN = auto()
    LLM_RESPONSE_COMPLETED = auto()
    TTS_STARTED = auto()
    TTS_FIRST_AUDIO = auto()
    TTS_COMPLETED = auto()
    BOT_INTERRUPTED = auto()
    STATE_CHANGED = auto()
    SUMMARY_UPDATED = auto()
    SESSION_ENDED = auto()
    PIPELINE_ERROR = auto()

@dataclass
class Event:
    type: EventType
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)

class EventBus:
    """Asynchronous event bus for cross-module communication within a session."""
    def __init__(self):
        self._subscribers: Dict[EventType, list] = {event_type: [] for event_type in EventType}

    def subscribe(self, event_type: EventType, callback: Callable[[Event], Any]):
        if event_type in self._subscribers:
            self._subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                try:
                    import inspect
                    if inspect.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error in event handler for {event.type}: {e}")
