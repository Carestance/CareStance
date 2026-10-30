from typing import Optional
from app.realtime.config import config

class SarvamTTSProviderConfig:
    @staticmethod
    def create_sarvam_service(api_key: Optional[str] = None, voice_id: Optional[str] = None):
        try:
            from pipecat.services.sarvam.tts import SarvamTTSService
        except ImportError:
            raise RuntimeError("pipecat-ai[sarvam] is not installed")
            
        key = api_key if api_key is not None else config.sarvam_api_key
        if key is None:
            raise ValueError("Sarvam API key not provided or found in environment.")
        key = str(key).strip()
        if not key:
            raise ValueError("Sarvam API key not provided or found in environment.")

        vid = config.sarvam_voice_id if voice_id is None else voice_id
        vid = str(vid).strip() if vid is not None else config.sarvam_voice_id
        if not vid:
            vid = config.sarvam_voice_id

        # bulbul:v3 has a different speaker list from v2.
        # "anushka" (v2 default) is NOT compatible — explicitly pick a v3 speaker.
        # v3 compatible voices: neha, priya, ritu, ishita, pooja, rahul, aditya, rohan …
        DEFAULT_V3_VOICE = "ritu"
        effective_voice = vid if vid else DEFAULT_V3_VOICE
        settings = SarvamTTSService.Settings(
            model="bulbul:v3",
            voice=effective_voice,
            pace=1.1
        )
        return SarvamTTSService(
            api_key=key,
            settings=settings,
            sample_rate=24000
        )
