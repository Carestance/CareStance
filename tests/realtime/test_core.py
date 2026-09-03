import pytest
import asyncio
from app.realtime.state.machine import StateMachine, State
from app.realtime.events.bus import EventBus, Event, EventType

@pytest.mark.asyncio
async def test_event_bus():
    bus = EventBus()
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
        
    bus.subscribe(EventType.SESSION_CREATED, handler)
    
    await bus.publish(Event(type=EventType.SESSION_CREATED, session_id="123", data={"test": "data"}))
    await asyncio.sleep(0.01) # Allow async task to run
    
    assert len(received_events) == 1
    assert received_events[0].session_id == "123"
    assert received_events[0].data["test"] == "data"

@pytest.mark.asyncio
async def test_fsm_valid_transitions():
    bus = EventBus()
    fsm = StateMachine("session_1", bus)
    
    assert fsm.current_state == State.INITIALIZING
    assert fsm.transition_to(State.READY) == True
    assert fsm.current_state == State.READY
    assert fsm.transition_to(State.LISTENING) == True
    
    # Invalid transition
    assert fsm.transition_to(State.BOT_SPEAKING) == False
    assert fsm.current_state == State.LISTENING

@pytest.mark.asyncio
async def test_fsm_interruption():
    bus = EventBus()
    fsm = StateMachine("session_1", bus)
    fsm.current_state = State.BOT_SPEAKING # Force state for testing
    
    # Valid interruption
    assert fsm.transition_to(State.INTERRUPTED) == True
    assert fsm.current_state == State.INTERRUPTED
    
    # Back to listening
    assert fsm.transition_to(State.LISTENING) == True
    assert fsm.current_state == State.LISTENING

@pytest.mark.asyncio
async def test_session_manager():
    from app.realtime.session.manager import SessionManager
    manager = SessionManager()
    session = manager.create_session("client_1")
    
    assert session.client_id == "client_1"
    assert session.session_id is not None
    assert manager.get_session(session.session_id) == session
    
    manager.remove_session(session.session_id)
    assert manager.get_session(session.session_id) is None

@pytest.mark.asyncio
async def test_pipeline_runner():
    from app.realtime.orchestration.pipeline_runner import PipelineRunner
    bus = EventBus()
    fsm = StateMachine("session_1", bus)
    runner = PipelineRunner("session_1", bus, fsm)
    
    await runner.start()
    assert runner._is_running == True
    assert fsm.current_state == State.READY
    
    await runner.stop()
    assert runner._is_running == False
    assert fsm.current_state == State.ENDING

@pytest.mark.asyncio
async def test_pipecat_event_bridge():
    from app.realtime.pipecat.event_bridge import PipecatEventBridge
    bus = EventBus()
    fsm = StateMachine("session_1", bus)
    bridge = PipecatEventBridge("session_1", bus, fsm)
    
    fsm.transition_to(State.READY)
    fsm.transition_to(State.LISTENING)
    
    # Simulate user speaking
    await bridge.on_user_started_speaking()
    assert fsm.current_state == State.USER_SPEAKING
    
    # Simulate user stopping
    await bridge.on_user_stopped_speaking()
    assert fsm.current_state == State.PROCESSING
    
    # Simulate LLM start
    await bridge.on_llm_start()
    assert fsm.current_state == State.LLM_GENERATING
    
    # Simulate TTS start
    await bridge.on_tts_first_audio()
    assert fsm.current_state == State.BOT_SPEAKING
    
    # Simulate interruption
    await bridge.on_user_started_speaking()
    assert fsm.current_state == State.USER_SPEAKING
