class PipecatAdapter:
    """Isolates Pipecat initialization and configuration logic."""
    def __init__(self, config):
        self.config = config

    def create_transport(self):
        pass

    def create_pipeline(self):
        # We only construct the providers if pipecat is available.
        from app.realtime.providers.stt.deepgram import STTProviderConfig
        from app.realtime.providers.llm.groq import LLMProviderConfig
        from app.realtime.providers.tts.cartesia import TTSProviderConfig
        from app.realtime.providers.stt.sarvam import SarvamSTTProviderConfig
        from app.realtime.providers.tts.sarvam import SarvamTTSProviderConfig
        
        # Fallbacks
        fallback_stt = STTProviderConfig.create_deepgram_service()
        fallback_tts = TTSProviderConfig.create_cartesia_service()
        
        # Primary
        primary_stt = SarvamSTTProviderConfig.create_sarvam_service()
        primary_tts = SarvamTTSProviderConfig.create_sarvam_service()
        
        llm = LLMProviderConfig.create_groq_service()
        
        return {
            "stt": primary_stt, 
            "llm": llm, 
            "tts": primary_tts,
            "fallback_stt": fallback_stt,
            "fallback_tts": fallback_tts
        }
