from typing import Optional
from app.realtime.config import config

class TTSProviderConfig:
    @staticmethod
    def create_cartesia_service(api_key: Optional[str] = None, voice_id: Optional[str] = None):
        try:
            from pipecat.services.cartesia.tts import CartesiaTTSService
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")
            
        key = api_key if api_key is not None else config.cartesia_api_key
        if key is None:
            raise ValueError("Cartesia API key not provided or found in environment.")
        key = str(key).strip()
        if not key:
            raise ValueError("Cartesia API key not provided or found in environment.")

        vid = config.cartesia_voice_id if voice_id is None else voice_id
        if vid is None:
            vid = config.cartesia_voice_id
        vid = str(vid).strip() or config.cartesia_voice_id

        from pipecat.services.tts_service import TextAggregationMode
        settings = CartesiaTTSService.Settings(
            voice=vid,
            model="sonic-3.5"
        )
        return CartesiaTTSService(
            api_key=key,
            settings=settings,
            # Stream LLM tokens as they arrive instead of waiting for sentence
            # punctuation. Disable Cartesia's managed buffer as well; in TOKEN
            # mode its default can otherwise add up to 3 seconds of delay.
            text_aggregation_mode=TextAggregationMode.TOKEN,
            max_buffer_delay_ms=0,
        )
