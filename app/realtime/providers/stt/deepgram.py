from typing import Optional
from app.realtime.config import config

class STTProviderConfig:
    @staticmethod
    def create_deepgram_service(api_key: Optional[str] = None):
        try:
            from pipecat.services.deepgram.stt import DeepgramSTTService
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")
            
        key = api_key if api_key is not None else config.deepgram_api_key
        if key is None:
            raise ValueError("Deepgram API key not provided or found in environment.")
        key = str(key).strip()
        if not key:
            raise ValueError("Deepgram API key not provided or found in environment.")

        return DeepgramSTTService(
            api_key=key,
            settings=DeepgramSTTService.Settings(
                model="nova-2-conversationalai",
                language="en",
                endpointing=100,
                interim_results=True
            )
        )
