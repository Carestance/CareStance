from typing import Optional
from app.realtime.config import config

class SarvamSTTProviderConfig:
    @staticmethod
    def create_sarvam_service(api_key: Optional[str] = None):
        try:
            from pipecat.services.sarvam.stt import SarvamSTTService
        except ImportError:
            raise RuntimeError("pipecat-ai[sarvam] is not installed")
            
        key = api_key or config.sarvam_api_key
        if not key:
            raise ValueError("Sarvam API key not provided or found in environment.")
            
        return SarvamSTTService(
            api_key=key,
            settings=SarvamSTTService.Settings(model="saaras:v3")
        )
