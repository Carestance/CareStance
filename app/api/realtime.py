from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.realtime.transport.webrtc import WebRTCOffer
from app.realtime.session.manager import manager as session_manager
from app.database import get_db

router = APIRouter()

@router.post("/webrtc/offer")
async def webrtc_offer(request: Request, offer: WebRTCOffer, db = Depends(get_db)):
    """
    Handles WebRTC SDP offers from the client to establish a real-time connection.
    """
    from app.main import get_current_user # Moved here to prevent circular import
    user = await get_current_user(request, db)
    # user can be None for anonymous demo sessions, or we enforce login depending on app logic
    user_id = user.id if user else None
    
    # Retrieve client_id from headers (to track session continuity across reconnects)
    client_id = request.headers.get("X-Client-ID", "anonymous")
    
    try:
        print(f"WEBRTC_OFFER_RECEIVED for client_id {client_id}", flush=True)
        # Create an isolated conversational session
        session = session_manager.create_session(client_id=client_id, user_id=user_id)
        
        # 1. Initialize WebRTC connection
        from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
        from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
        from pipecat.transports.base_transport import TransportParams
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator, LLMUserAggregator, LLMContext, LLMContextFrame
        import asyncio
        
        # Initialize connection with production ICE Servers for NAT Traversal
        import os
        from aiortc import RTCIceServer, RTCConfiguration
        
        turn_url = os.getenv("TURN_SERVER_URL")
        ice_servers = [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
        
        if turn_url:
            turn_user = os.getenv("TURN_USERNAME")
            turn_pass = os.getenv("TURN_PASSWORD")
            ice_servers.append(
                RTCIceServer(urls=[turn_url], username=turn_user, credential=turn_pass)
            )
            print("DEBUG: Loaded external TURN credentials for production WebRTC.", flush=True)

        webrtc_conn = SmallWebRTCConnection(
            ice_servers=ice_servers
        )
        print("WEBRTC_CONNECTION_CREATED", flush=True)
        
        # Initialize transport
        transport = SmallWebRTCTransport(
            webrtc_connection=webrtc_conn,
            params=TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                camera_out_enabled=False,
                vad_enabled=True,
            )
        )
        print("TRANSPORT_INITIALIZED", flush=True)
        
        # 2. Build Pipeline Components
        from app.realtime.orchestration.pipeline_builder import PipelineBuilder
        # Note: EventBus and FSM are required for PipelineBuilder in our architecture
        from app.realtime.events.bus import EventBus
        from app.realtime.state.machine import StateMachine
        event_bus = EventBus()
        fsm = StateMachine(session.session_id, event_bus)
        builder = PipelineBuilder(session.session_id, event_bus, fsm)
        
        # 3. Load Context
        print("CONTEXT_LOADED", flush=True)
        built_pipeline = await builder.build(user_id, db)
        components = built_pipeline["components"]
        
        stt = components["stt"]
        print("DEEPGRAM_INITIALIZED", flush=True)
        llm = components["llm"]
        print("GROQ_INITIALIZED", flush=True)
        tts = components["tts"]
        print("CARTESIA_INITIALIZED", flush=True)
        
        # 4. Construct the DAG
        messages = [
            {"role": "system", "content": built_pipeline["system_prompt"]},
            {"role": "user", "content": "Hello! I am ready to begin my deep dive assessment."},
        ]
        
        async def mark_conversation_complete(params: dict):
            """Marks the deep dive conversation as completed when you have collected enough evidence."""
            print("LLM requested conversation completion!", flush=True)
            session.is_closing = True
            return {"status": "success", "message": "Closing sequence initiated."}
            
        context = LLMContext(messages=messages, tools=[mark_conversation_complete])
            
        async def save_completion_state():
            print("Persisting canonical transcript to database...", flush=True)
            from app.database import AsyncSessionLocal
            from sqlalchemy.future import select
            from app.models import AssessmentResult
            async with AsyncSessionLocal() as session_db:
                result = (await session_db.execute(select(AssessmentResult).where(AssessmentResult.user_id == user_id))).scalars().first()
                if result:
                    history = [{"role": msg.get("role"), "content": msg.get("content")} for msg in context.messages if msg.get("role") in ("user", "assistant")]
                    result.chat_messages = history
                    result.phase3_result = "COMPLETED"
                    await session_db.commit()
            print("Transcript persisted.", flush=True)

        context_aggregator = LLMUserAggregator(context)
        assistant_aggregator = LLMAssistantAggregator(context)
        
        from app.realtime.pipecat.broadcaster import TranscriptBroadcaster
        broadcaster = TranscriptBroadcaster(session=session, on_complete=save_completion_state)

        pipeline = Pipeline([
            transport.input(),
            stt,
            context_aggregator,
            llm,
            tts,
            broadcaster,
            transport.output(),
            assistant_aggregator
        ])
        print("PIPELINE_BUILT", flush=True)
        
        # 5. Create Task and Runner
        pipeline_task = PipelineTask(pipeline)
        print("PIPELINE_TASK_CREATED", flush=True)
        
        runner = PipelineRunner()
        
        @transport.event_handler("on_client_connected")
        async def on_client_connected(t, client):
            print("PIPELINE_READY", flush=True)
            print("GREETING_QUEUED", flush=True)
            # Queue the context frame which triggers the LLM to process the system prompt and generate the first response!
            await pipeline_task.queue_frames([LLMContextFrame(context)])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(t, client):
            print("SESSION_DISCONNECTED", flush=True)
            import asyncio
            asyncio.create_task(session_manager.cleanup_session(session.session_id))
        
        # We must initialize the WebRTC connection with the incoming SDP offer
        await webrtc_conn.initialize(offer.sdp, offer.type)
        
        # We must run the pipeline in the background so it doesn't block the endpoint
        runtime_task = asyncio.create_task(runner.run(pipeline_task))
        print("PIPELINE_RUNNER_STARTED", flush=True)
        
        # Save to session manager so we can clean it up later
        session.webrtc_conn = webrtc_conn
        session.transport = transport
        session.runner_task = runtime_task
        session.pipeline_task = pipeline_task
        session.pipeline_runner = runner
        session.context = context
        
        return JSONResponse({
            "status": "success",
            "session_id": session.session_id,
            "sdp": webrtc_conn.get_answer()["sdp"],
            "type": webrtc_conn.get_answer()["type"]
        })
    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
