from app.realtime.events.bus import EventBus
from app.realtime.state.machine import StateMachine

class PipelineBuilder:
    """Builds the Pipecat pipeline using configured providers."""
    
    def __init__(self, session_id: str, event_bus: EventBus, fsm: StateMachine):
        self.session_id = session_id
        self.event_bus = event_bus
        self.fsm = fsm
        
    async def build(self, user_id: int = None, db = None):
        """
        Constructs the DAG pipeline and initializes ChatContext.
        """
        from app.realtime.memory.context_loader import ContextLoader
        from app.realtime.pipecat.adapter import PipecatAdapter
        from app.realtime.config import config
        from app.pipeline.prompts_phase3 import LIVE_CHAT_PROMPT
        import json
        
        # 1. Load Context
        context_data = await ContextLoader.load_user_context(user_id, db) if db else {"name": "Guest", "grade": "Unknown", "archetype": "Unknown", "recommended_path": "Unknown", "interests": []}
        all_interests = ", ".join(context_data.get("interests", [])) if context_data.get("interests") else "your fields of interest"
        
        sys_prompt = LIVE_CHAT_PROMPT.format(
            context_json=json.dumps(context_data, indent=2),
            student_name=context_data["name"],
            all_interests=all_interests
        )

        # 2. Initialize Adapter
        adapter = PipecatAdapter(config)
        
        # 3. Build pipeline components
        pipeline_components = adapter.create_pipeline()
        
        # In the full implementation, we'd initialize the Pipecat `Pipeline`, `PipelineTask`,
        # and `ChatContext` here. For Phase 6, we establish the context loading.
        
        return {
            "status": "built", 
            "session_id": self.session_id,
            "system_prompt": sys_prompt,
            "components": pipeline_components
        }
