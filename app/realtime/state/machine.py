from enum import Enum, auto
from typing import Optional
from app.realtime.events.bus import EventBus, Event, EventType

class State(Enum):
    INITIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    USER_SPEAKING = auto()
    PROCESSING = auto()
    LLM_GENERATING = auto()
    BOT_SPEAKING = auto()
    INTERRUPTED = auto()
    ENDING = auto()
    ENDED = auto()
    ERROR = auto()

class StateMachine:
    """Finite State Machine for managing conversational state."""
    
    # Define valid transitions from each state
    VALID_TRANSITIONS = {
        State.INITIALIZING: {State.READY, State.ERROR},
        State.READY: {State.LISTENING, State.ERROR, State.ENDING},
        State.LISTENING: {State.USER_SPEAKING, State.ERROR, State.ENDING},
        State.USER_SPEAKING: {State.PROCESSING, State.LISTENING, State.ERROR},
        State.PROCESSING: {State.LLM_GENERATING, State.LISTENING, State.ERROR},
        State.LLM_GENERATING: {State.BOT_SPEAKING, State.INTERRUPTED, State.ERROR},
        State.BOT_SPEAKING: {State.LISTENING, State.INTERRUPTED, State.ERROR},
        State.INTERRUPTED: {State.LISTENING, State.USER_SPEAKING, State.ERROR},
        State.ENDING: {State.ENDED, State.ERROR},
        State.ENDED: set(),
        State.ERROR: {State.ENDING}
    }

    def __init__(self, session_id: str, event_bus: EventBus):
        self.session_id = session_id
        self.event_bus = event_bus
        self.current_state = State.INITIALIZING

    def transition_to(self, new_state: State, reason: str = "") -> bool:
        if new_state in self.VALID_TRANSITIONS.get(self.current_state, set()):
            old_state = self.current_state
            self.current_state = new_state
            
            # Fire and forget an event notifying of the change
            import asyncio
            asyncio.create_task(
                self.event_bus.publish(Event(
                    type=EventType.STATE_CHANGED,
                    session_id=self.session_id,
                    data={"old_state": old_state.name, "new_state": new_state.name, "reason": reason}
                ))
            )
            return True
        else:
            print(f"Invalid transition from {self.current_state} to {new_state} in session {self.session_id}")
            return False
