import logging


logger = logging.getLogger(__name__)


class PipecatAdapter:
    """Isolates Pipecat initialization and configuration logic."""
    def __init__(self, config):
        self.config = config

    def create_transport(self):
        pass

    def create_pipeline(self):
        import os
        from app.realtime.providers.stt.deepgram import STTProviderConfig
        from app.realtime.providers.llm.groq import LLMProviderConfig
        from app.realtime.providers.tts.cartesia import TTSProviderConfig

        stt = None
        tts = None
        
        # 1. STT Provider: Prioritize Deepgram (low-latency, resilient against echo/false interruptions)
        if os.getenv("DEEPGRAM_API_KEY"):
            try:
                stt = STTProviderConfig.create_deepgram_service()
            except Exception as exc:
                logger.warning("Deepgram STT initialization failed (%s).", type(exc).__name__)

        if not stt and os.getenv("SARVAM_API_KEY"):
            try:
                from app.realtime.providers.stt.sarvam import SarvamSTTProviderConfig
                stt = SarvamSTTProviderConfig.create_sarvam_service()
            except Exception as exc:
                logger.warning("Sarvam STT initialization failed (%s).", type(exc).__name__)

        if not stt:
            raise RuntimeError(
                "No speech-to-text provider could be initialized. Configure DEEPGRAM_API_KEY "
                "or SARVAM_API_KEY and install the matching Pipecat provider."
            )
        logger.info("Initialized speech-to-text provider: %s", type(stt).__name__)

        # 2. TTS Provider: Prioritize Sarvam (Indian natural voices: Ritu / Neha)
        if os.getenv("SARVAM_API_KEY"):
            try:
                from app.realtime.providers.tts.sarvam import SarvamTTSProviderConfig
                tts = SarvamTTSProviderConfig.create_sarvam_service()
            except Exception as e:
                tts = None

        if not tts and os.getenv("CARTESIA_API_KEY"):
            try:
                tts = TTSProviderConfig.create_cartesia_service()
            except Exception as e:
                tts = None

        llm = LLMProviderConfig.create_groq_service()
        
        return {
            "stt": stt, 
            "llm": llm, 
            "tts": tts
        }

