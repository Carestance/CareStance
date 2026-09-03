import time
import logging

logger = logging.getLogger(__name__)

class LatencyProfiler:
    """Measures and logs key latency metrics for the real-time pipeline."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._user_speech_start = 0
        self._user_speech_end = 0
        self._llm_start = 0
        self._tts_first_audio = 0

    def mark_user_speech_start(self):
        self._user_speech_start = time.time()
        
    def mark_user_speech_end(self):
        self._user_speech_end = time.time()
        
    def mark_llm_start(self):
        self._llm_start = time.time()
        
    def mark_tts_first_audio(self):
        self._tts_first_audio = time.time()
        self._log_metrics()

    def _log_metrics(self):
        if not (self._user_speech_end and self._tts_first_audio):
            return
            
        ttfa = (self._tts_first_audio - self._user_speech_end) * 1000
        llm_latency = (self._llm_start - self._user_speech_end) * 1000 if self._llm_start else 0
        tts_latency = (self._tts_first_audio - self._llm_start) * 1000 if self._llm_start else 0
        
        logger.info(
            f"Latency Metrics [Session: {self.session_id}]: "
            f"TTFA: {ttfa:.0f}ms | "
            f"LLM Processing: {llm_latency:.0f}ms | "
            f"TTS Processing: {tts_latency:.0f}ms"
        )
