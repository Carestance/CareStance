from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame, TranscriptionFrame, TextFrame, OutputTransportMessageFrame, 
    InterimTranscriptionFrame, TTSStoppedFrame, BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame
)
import json

class TranscriptBroadcaster(FrameProcessor):
    """
    Intercepts TranscriptionFrame (from STT), TextFrame (from LLM), and Bot speaking frames
    and broadcasts them to the WebRTC Data Channel via OutputTransportMessageFrame.
    Also handles TTSStoppedFrame to emit conversation completion after AI finishes speaking.
    """
    def __init__(
        self,
        session,
        on_complete=None,
        *,
        broadcast_transcripts=True,
        broadcast_assistant=True,
    ):
        super().__init__()
        self.session = session
        self.on_complete = on_complete
        self.broadcast_transcripts = broadcast_transcripts
        self.broadcast_assistant = broadcast_assistant
        self._current_assistant_text = ""
        
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        # Broadcast final transcripts from STT
        if self.broadcast_transcripts and isinstance(
            frame, (TranscriptionFrame, InterimTranscriptionFrame)
        ):
            if isinstance(frame, TranscriptionFrame) and getattr(frame, "finalized", False):
                msg = {
                    "type": "TRANSCRIPT_FINAL",
                    "role": "user",
                    "text": frame.text
                }
                out_frame = OutputTransportMessageFrame(message=msg)
                await self.push_frame(out_frame, direction)
            else:
                msg = {
                    "type": "TRANSCRIPT_PARTIAL",
                    "role": "user",
                    "text": frame.text
                }
                out_frame = OutputTransportMessageFrame(message=msg)
                await self.push_frame(out_frame, direction)
                
        # Accumulate LLM responses
        elif self.broadcast_assistant and isinstance(frame, TextFrame) and not isinstance(
            frame, (TranscriptionFrame, InterimTranscriptionFrame)
        ):
            self._current_assistant_text += frame.text

        # Broadcast speaking state
        elif self.broadcast_assistant and isinstance(frame, BotStartedSpeakingFrame):
            msg = {"type": "BOT_STARTED_SPEAKING"}
            out_frame = OutputTransportMessageFrame(message=msg)
            await self.push_frame(out_frame, direction)

        elif self.broadcast_assistant and isinstance(frame, BotStoppedSpeakingFrame):
            msg = {"type": "BOT_STOPPED_SPEAKING"}
            out_frame = OutputTransportMessageFrame(message=msg)
            await self.push_frame(out_frame, direction)

        # Emit accumulated text on TTS complete
        elif self.broadcast_assistant and isinstance(frame, TTSStoppedFrame):
            if self._current_assistant_text.strip():
                msg = {
                    "type": "ASSISTANT_MESSAGE",
                    "role": "assistant",
                    "text": self._current_assistant_text.strip()
                }
                out_frame = OutputTransportMessageFrame(message=msg)
                await self.push_frame(out_frame, direction)
                self._current_assistant_text = ""
                
            if getattr(self.session, 'is_closing', False) and not getattr(self.session, 'is_completed', False):
                self.session.is_completed = True
                msg = {
                    "type": "CONVERSATION_COMPLETED",
                    "assessment_id": self.session.session_id,
                    "session_id": self.session.session_id,
                    "can_finalize": True
                }
                out_frame = OutputTransportMessageFrame(message=msg)
                await self.push_frame(out_frame, direction)
                if self.on_complete:
                    await self.on_complete()

        # IMPORTANT: Forward the original frame downstream (including AudioRawFrame!)
        await self.push_frame(frame, direction)
