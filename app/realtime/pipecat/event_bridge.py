from app.realtime.events.bus import EventBus, Event, EventType
from app.realtime.state.machine import StateMachine, State
from app.realtime.orchestration.latency_profiler import LatencyProfiler
import asyncio

class PipecatEventBridge:
    """Translates Pipecat events into application events and manages FSM transitions."""
    def __init__(self, session_id: str, event_bus: EventBus, fsm: StateMachine):
        self.session_id = session_id
        self.event_bus = event_bus
        self.fsm = fsm
        self.profiler = LatencyProfiler(session_id)

    async def on_user_started_speaking(self):
        """Called by Pipecat when VAD detects speech."""
        self.profiler.mark_user_speech_start()
        if self.fsm.current_state in [State.BOT_SPEAKING, State.LLM_GENERATING]:
            self.fsm.transition_to(State.INTERRUPTED, reason="user_barge_in")
        
        self.fsm.transition_to(State.USER_SPEAKING)
        await self.event_bus.publish(Event(
            type=EventType.USER_SPEECH_STARTED,
            session_id=self.session_id
        ))

    async def on_user_stopped_speaking(self):
        """Called by Pipecat when VAD detects silence."""
        self.profiler.mark_user_speech_end()
        self.fsm.transition_to(State.PROCESSING)
        await self.event_bus.publish(Event(
            type=EventType.USER_SPEECH_STOPPED,
            session_id=self.session_id
        ))
        
    async def on_llm_start(self):
        self.profiler.mark_llm_start()
        self.fsm.transition_to(State.LLM_GENERATING)
        await self.event_bus.publish(Event(type=EventType.LLM_REQUEST_STARTED, session_id=self.session_id))
        
    async def on_tts_start(self):
        # We define TTS start as the moment we begin synthesizing, but TTFA is when first audio plays.
        # We can record the start event here for tracking.
        pass

    async def on_tts_first_audio(self):
        self.profiler.mark_tts_first_audio()
        self.fsm.transition_to(State.BOT_SPEAKING)
        await self.event_bus.publish(Event(type=EventType.TTS_FIRST_AUDIO, session_id=self.session_id))
        
    async def on_tts_end(self):
        self.fsm.transition_to(State.LISTENING)
        await self.event_bus.publish(Event(type=EventType.TTS_COMPLETED, session_id=self.session_id))
