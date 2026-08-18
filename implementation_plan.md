# CareStance Real-Time Conversational AI Agent Implementation Plan

## 1. Current Architecture Findings
The existing "Career Buddy" is implemented as a semi-stateful, request-response HTTP system. 
- **API Routes**: Interaction happens through multiple synchronous/asynchronous endpoints (`/chatbot/message`, `/assessment/phase3/chat_v2`, `/roadmap/step/.../chat`) in `app/main.py`.
- **LLM Integration**: Uses Groq (Llama 3.3) directly inside HTTP handlers, blocking until generation is complete.
- **Frontend**: The `frontend/static/js/voice_client.js` script provides a Web Speech API (browser STT/TTS) fallback and makes HTTP POST requests. It attempts to use a WebSocket, but the backend WebSocket router has been removed.
- **State/Memory**: Conversations are fetched via standard SQL queries (e.g., pulling the last 10 `ChatMessage` records). There is no rolling summary, just hard-coded context injection.
- **Real-Time Capabilities**: None currently exist on the backend. No WebRTC, no Pipecat, and no streaming audio.

## 2. Files That Need Modification
- **`app/main.py`**: Will require registering the new WebRTC/real-time signaling routes and initializing the `SessionManager`. 
- **`frontend/static/js/voice_client.js`**: Must be rewritten to use `RTCPeerConnection` (WebRTC) rather than the local Web Speech API and HTTP fetch.
- **`frontend/templates/chatbot.html`, `assessment_phase3_v2.html`, `roadmap_step_chat.html`**: UI updates to reflect WebRTC connection states (Connecting, Listening, Speaking, etc.) without altering the core layout.
- **`requirements.txt`**: Add dependencies: `pipecat-ai`, `deepgram-sdk`, `cartesia`, `aiortc` (for WebRTC signaling).
- **`app/models.py`**: Schema additions for persistent conversation summaries.

## 3. New Files & Modules (Backend Structure)
```text
app/
├── api/
│   └── realtime.py (FastAPI WebRTC signaling / SDP exchange)
├── realtime/
│   ├── session/
│   │   ├── manager.py
│   │   └── models.py
│   ├── state/
│   │   ├── machine.py
│   │   └── states.py
│   ├── events/
│   │   ├── bus.py
│   │   └── events.py
│   ├── orchestration/
│   │   ├── dag.py
│   │   ├── pipeline_builder.py
│   │   └── pipeline_runner.py
│   ├── pipecat/
│   │   ├── adapter.py
│   │   └── event_bridge.py
│   ├── providers/
│   │   ├── stt/deepgram.py
│   │   ├── llm/groq.py
│   │   └── tts/cartesia.py
│   ├── memory/
│   │   ├── repository.py
│   │   ├── context_loader.py
│   │   └── summarizer.py
│   ├── transport/
│   │   └── webrtc.py
│   ├── observability/
│   │   ├── latency.py
│   │   └── logging.py
│   └── config.py
```

## 4. Database/Schema Changes
Add a new model in `app/models.py` to persist cross-session memory without overloading `ChatMessage`:
```python
class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    summary_text = Column(Text, default="")
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
```
*Note: Assessment results (`models.AssessmentResult`) will be queried directly via `user_id` as read-only context.*

## 5. Proposed Event Definitions
The Event Bus will handle:
- `SESSION_CREATED`, `SESSION_READY`
- `CLIENT_CONNECTED`, `CLIENT_DISCONNECTED`
- `USER_SPEECH_STARTED`, `USER_SPEECH_STOPPED`
- `TRANSCRIPT_PARTIAL`, `TRANSCRIPT_FINAL`
- `LLM_REQUEST_STARTED`, `LLM_FIRST_TOKEN`, `LLM_RESPONSE_COMPLETED`
- `TTS_STARTED`, `TTS_FIRST_AUDIO`, `TTS_COMPLETED`
- `BOT_INTERRUPTED`
- `STATE_CHANGED`, `SUMMARY_UPDATED`, `SESSION_ENDED`, `PIPELINE_ERROR`

## 6. Proposed FSM States & Transition Table
**States**: `INITIALIZING`, `READY`, `LISTENING`, `USER_SPEAKING`, `PROCESSING`, `LLM_GENERATING`, `BOT_SPEAKING`, `INTERRUPTED`, `ENDING`, `ENDED`, `ERROR`

**Key Transitions**:
- `READY` → (Client connects) → `LISTENING`
- `LISTENING` → (User speech start) → `USER_SPEAKING`
- `USER_SPEAKING` → (Silence/Turn end) → `PROCESSING`
- `PROCESSING` → (LLM active) → `LLM_GENERATING`
- `LLM_GENERATING` → (TTS active) → `BOT_SPEAKING`
- `BOT_SPEAKING` → (TTS complete) → `LISTENING`
- `BOT_SPEAKING` or `LLM_GENERATING` → (User speech start) → `INTERRUPTED`
- `INTERRUPTED` → (Cancel queues/stop audio) → `LISTENING` or `USER_SPEAKING`

## 7. Proposed DAG (Directed Acyclic Graph)
1. **Audio Input (WebRTC)** → VAD (Voice Activity Detection)
2. **VAD** → Deepgram STT (Streaming)
3. **STT (Final Transcript)** → Context Enrichment (Injecting DB Summary/Assessment)
4. **Context Enrichment** → Groq LLM (Streaming Tokens)
5. **Groq LLM** → Cartesia TTS (Streaming Audio)
6. **Cartesia TTS** → WebRTC Audio Output
*Parallel Async Branches: Event Bus Logging, Summary Persistence.*

## 8. Pipecat Integration Strategy
- **Isolation**: Use `app/realtime/pipecat/adapter.py` to wrap Pipecat's `Pipeline` and `PipelineTask`. The application logic will not import Pipecat directly.
- **Event Bridging**: `app/realtime/pipecat/event_bridge.py` will translate Pipecat callbacks (e.g., `on_user_started_speaking()`) into internal `EventBus` events (e.g., `USER_SPEECH_STARTED`), keeping the FSM decoupled.

## 9. WebRTC Integration Strategy
- **Backend**: Use `aiortc` (via Pipecat's native WebRTC transport module) to handle WebRTC SDP Offers and Answers.
- **Signaling**: A FastAPI endpoint `/api/realtime/webrtc-offer` will accept the SDP offer from the browser, create a Pipecat WebRTC transport, run the pipeline, and return the SDP answer.
- **Frontend**: `voice_client.js` will initialize a standard `RTCPeerConnection`, gather microphone streams, and attach incoming remote streams to a hidden `<audio>` element.

## 10. Provider Configuration
- **STT**: Deepgram (Model: Nova-2). Configured for low-latency streaming and endpointing.
- **LLM**: Groq (Model: `llama-3.3-70b-versatile`).
- **TTS**: Cartesia (Model: Sonic, Voice: Arushi).
- **Secrets**: Sourced strictly from `.env` via a new configuration module (`app/realtime/config.py`).

## 11. Career Buddy Migration Strategy
1. Build the WebRTC real-time agent entirely in parallel inside the `app/realtime` module.
2. The legacy HTTP routes (`/assessment/phase3/chat_v2`, etc.) remain fully functional during development.
3. Update `frontend/static/js/voice_client.js` to default to WebRTC, with HTTP fallback completely removed once stable.
4. Inject read-only assessment context (Archetype, interests, roadmap progress) into the real-time agent's initial prompt using `ContextLoader`.
5. Finally, deprecate and remove the old HTTP chat endpoints.

## 12. Testing Strategy
- **Unit Tests**: `tests/realtime/` will test FSM transitions independently of audio.
- **Mocks**: Mock the STT, LLM, and TTS providers to test the Pipeline Runner and Pipeline Builder dynamically.
- **Interruption Test**: Simulate a sequence of events (`TTS_STARTED` followed immediately by `USER_SPEECH_STARTED`) to guarantee cancellation hooks fire.
- **Concurrency**: Spin up 5 dummy sessions simultaneously and ensure `session_id` isolation holds.

## 13. Latency Measurement Strategy
- Add a lightweight listener to the Event Bus specifically for latency.
- Measure: 
  - `TTFT` (LLM First Token Time) = `LLM_FIRST_TOKEN` - `TRANSCRIPT_FINAL`
  - `TTFA` (Time To First Audio) = `TTS_FIRST_AUDIO` - `TRANSCRIPT_FINAL`
- Log this as a structured JSON object at the end of each turn. Avoid making blocking DB writes during the turn.

## 14. Implementation Order (Phase-by-Phase)
1. **Phase 1**: Architecture Plan (Completed - this document).
2. **Phase 2**: Add requirements, database schema (`ConversationSummary`), and basic config logic.
3. **Phase 3**: Core Orchestration (FSM, Event Bus, Session Manager).
4. **Phase 4**: Provider Adapters & Pipecat Wrapper (Deepgram, Groq, Cartesia).
5. **Phase 5**: WebRTC Transport & Frontend update (`voice_client.js`).
6. **Phase 6**: Persistence Integration (Context Loader & Summary updater).
7. **Phase 7**: E2E Integration, Latency Profiling, and Interruption stabilization.
8. **Phase 8**: Deprecate old Career Buddy HTTP endpoints.

