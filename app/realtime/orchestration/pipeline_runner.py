import asyncio
from typing import Optional
from app.realtime.events.bus import EventBus, Event, EventType
from app.realtime.state.machine import StateMachine, State

class PipelineRunner:
    """Manages the execution of the conversational pipeline."""
    def __init__(self, session_id: str, event_bus: EventBus, fsm: StateMachine):
        self.session_id = session_id
        self.event_bus = event_bus
        self.fsm = fsm
        self._task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        if self._is_running:
            return
        
        self._is_running = True
        self.fsm.transition_to(State.READY)
        
        # In a real implementation, this will initialize the Pipecat pipeline
        # and block on pipeline.run()
        self._task = asyncio.create_task(self._mock_pipeline_loop())

    async def _mock_pipeline_loop(self):
        try:
            while self._is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self._is_running = False
            self.fsm.transition_to(State.ENDED)
            await self.event_bus.publish(Event(type=EventType.SESSION_ENDED, session_id=self.session_id))

    async def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.fsm.transition_to(State.ENDING)
