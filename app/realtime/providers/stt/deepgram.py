from typing import Optional
from app.realtime.config import config

class STTProviderConfig:
    @staticmethod
    def create_deepgram_service(api_key: Optional[str] = None):
        try:
            from pipecat.services.deepgram.stt import DeepgramSTTService
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")
            
        key = api_key or config.deepgram_api_key
        if not key:
            raise ValueError("Deepgram API key not provided or found in environment.")
            
        return DeepgramSTTService(
            api_key=key,
            model="nova-2-conversationalai"
        )
