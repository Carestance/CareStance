from typing import Optional
from app.realtime.config import config

class TTSProviderConfig:
    @staticmethod
    def create_cartesia_service(api_key: Optional[str] = None, voice_id: Optional[str] = None):
        try:
            from pipecat.services.cartesia.tts import CartesiaTTSService
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")
            
        key = api_key or config.cartesia_api_key
        vid = voice_id or config.cartesia_voice_id
        
        if not key:
            raise ValueError("Cartesia API key not provided or found in environment.")
            
        return CartesiaTTSService(
            api_key=key,
            voice_id=vid,
            model="sonic-3.5" # Updated from sunsetted sonic to current stable model
        )
