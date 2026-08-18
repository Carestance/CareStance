import uuid
from typing import Dict, Optional
import datetime

from app.realtime.state.machine import StateMachine, State
from app.realtime.events.bus import EventBus, Event, EventType

class Session:
    """Represents an isolated realtime conversation session."""
    def __init__(self, client_id: str, user_id: Optional[int] = None):
        self.session_id = str(uuid.uuid4())
        self.client_id = client_id
        self.user_id = user_id
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.last_activity = self.created_at
        
        self.event_bus = EventBus()
        self.fsm = StateMachine(session_id=self.session_id, event_bus=self.event_bus)
        
        # Pipeline runtime context
        self.pipeline_runner = None
        self.pipeline_task = None
        self.runner_task = None
        self.transport = None
        self.webrtc_conn = None
        self.status = "ACTIVE"
        self.context = {} # Assessment context, rolling summary, etc.

    def touch(self):
        self.last_activity = datetime.datetime.now(datetime.timezone.utc)

class SessionManager:
    """Manages the lifecycle of all active real-time sessions."""
    def __init__(self):
        self._active_sessions: Dict[str, Session] = {}

    def create_session(self, client_id: str, user_id: Optional[int] = None) -> Session:
        session = Session(client_id, user_id)
        self._active_sessions[session.session_id] = session
        
        import asyncio
        asyncio.create_task(
            session.event_bus.publish(Event(
                type=EventType.SESSION_CREATED, 
                session_id=session.session_id,
                data={"client_id": client_id, "user_id": user_id}
            ))
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self._active_sessions.get(session_id)
        if session:
            session.touch()
        return session

    async def cleanup_session(self, session_id: str):
        """Idempotently cleans up all resources associated with a session."""
        session = self._active_sessions.get(session_id)
        if not session or session.status in ["CLEANING", "CLOSED"]:
            return
            
        session.status = "CLEANING"
        print(f"SESSION_CLEANUP_STARTED for {session_id}", flush=True)
        
        import asyncio
        
        try:
            # 1. Stop PipelineTask gracefully if running
            if session.pipeline_task and hasattr(session.pipeline_task, "cancel"):
                # pipecat cancel method
                try:
                    await session.pipeline_task.cancel()
                except Exception as e:
                    print(f"Error cancelling pipeline_task: {e}")

            # 2. Cancel runner asyncio.Task
            if session.runner_task and not session.runner_task.done():
                session.runner_task.cancel()
                try:
                    # Wait briefly for cancellation to process
                    await asyncio.wait_for(session.runner_task, timeout=2.0)
                except asyncio.CancelledError:
                    pass
                except asyncio.TimeoutError:
                    print("Timeout waiting for runner task to cancel")
                except Exception as e:
                    print(f"Error cancelling runner_task: {e}")

            # 3. Disconnect WebRTC Transport/Connection
            if session.webrtc_conn and hasattr(session.webrtc_conn, "close"):
                try:
                    session.webrtc_conn.close()
                except Exception:
                    pass
                    
            if session.transport and hasattr(session.transport, "close"):
                try:
                    session.transport.close()
                except Exception:
                    pass

        finally:
            session.status = "CLOSED"
            print(f"SESSION_CLEANED for {session_id}", flush=True)
            self._active_sessions.pop(session_id, None)

    async def shutdown_all(self):
        """Called during application shutdown (SIGINT/SIGTERM)."""
        print("APPLICATION_SHUTDOWN_STARTED", flush=True)
        print(f"ACTIVE_SESSIONS={len(self._active_sessions)}", flush=True)
        import asyncio
        
        session_ids = list(self._active_sessions.keys())
        tasks = [self.cleanup_session(sid) for sid in session_ids]
        
        if tasks:
            # Wait with a timeout for graceful shutdown
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for sid, res in zip(session_ids, results):
                if isinstance(res, Exception):
                    print(f"Failed to cleanup session {sid}: {res}")
                    
        print("APPLICATION_SHUTDOWN_COMPLETED", flush=True)

    def remove_session(self, session_id: str):
        # Fallback synchronous removal if needed, but cleanup_session is preferred
        if session_id in self._active_sessions:
            session = self._active_sessions.pop(session_id)
            session.status = "CLOSED"
            
    async def cleanup_sessions_for_user(self, user_id: int):
        import asyncio
        session_ids = [s.session_id for s in self._active_sessions.values() if s.user_id == user_id]
        if not session_ids:
            return
            
        tasks = [self.cleanup_session(sid) for sid in session_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
                
manager = SessionManager()
