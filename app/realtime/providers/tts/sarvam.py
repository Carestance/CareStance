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
            
        # bulbul:v3-beta has a different speaker list from v2.
        # "anushka" (v2 default) is NOT compatible — explicitly pick a v3-beta speaker.
        # v3-beta compatible voices: neha, priya, ritu, ishita, pooja, rahul, aditya, rohan …
        DEFAULT_V3_VOICE = "neha"
        effective_voice = vid if vid else DEFAULT_V3_VOICE
        settings = SarvamTTSService.Settings(
            model="bulbul:v3-beta",
            voice=effective_voice,
            pace=1.1
        )
        return SarvamTTSService(
            api_key=key,
            settings=settings,
            sample_rate=24000
        )
