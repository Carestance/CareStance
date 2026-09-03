from typing import Optional
from app.realtime.config import config

class SarvamTTSProviderConfig:
    @staticmethod
    def create_sarvam_service(api_key: Optional[str] = None, voice_id: Optional[str] = None):
        try:
            from pipecat.services.sarvam.tts import SarvamTTSService
        except ImportError:
            raise RuntimeError("pipecat-ai[sarvam] is not installed")
            
        key = api_key or config.sarvam_api_key
        vid = voice_id or config.sarvam_voice_id
        
        if not key:
            raise ValueError("Sarvam API key not provided or found in environment.")
            
        settings = SarvamTTSService.Settings(
            voice=vid,
            pace=1.1
        ) if vid else None
        return SarvamTTSService(
            api_key=key,
            settings=settings,
            sample_rate=24000
        )
