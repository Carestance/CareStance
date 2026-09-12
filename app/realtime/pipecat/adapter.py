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
        
        # Check if Sarvam is requested & available
        if os.getenv("SARVAM_API_KEY"):
            try:
                from app.realtime.providers.stt.sarvam import SarvamSTTProviderConfig
                from app.realtime.providers.tts.sarvam import SarvamTTSProviderConfig
                stt = SarvamSTTProviderConfig.create_sarvam_service()
                tts = SarvamTTSProviderConfig.create_sarvam_service()
            except Exception as e:
                stt = None
                tts = None

        if not stt:
            stt = STTProviderConfig.create_deepgram_service()
            
        if not tts:
            tts = TTSProviderConfig.create_cartesia_service()

        llm = LLMProviderConfig.create_groq_service()
        
        return {
            "stt": stt, 
            "llm": llm, 
            "tts": tts
        }

