import pytest
from unittest.mock import patch

def test_deepgram_config():
    from app.realtime.providers.stt.deepgram import STTProviderConfig
    stt = STTProviderConfig.create_deepgram_service(api_key="test-key")
    assert stt is not None
    
    with pytest.raises(ValueError):
        STTProviderConfig.create_deepgram_service(api_key="")

def test_groq_config():
    from app.realtime.providers.llm.groq import LLMProviderConfig
    llm = LLMProviderConfig.create_groq_service(api_key="test-key")
    assert llm is not None
    
    with pytest.raises(ValueError):
        LLMProviderConfig.create_groq_service(api_key="")

def test_cartesia_config():
    from app.realtime.providers.tts.cartesia import TTSProviderConfig
    tts = TTSProviderConfig.create_cartesia_service(api_key="test-key")
    assert tts is not None
    
    with pytest.raises(ValueError):
        TTSProviderConfig.create_cartesia_service(api_key="")

def test_adapter_pipeline_creation():
    from app.realtime.pipecat.adapter import PipecatAdapter
    from app.realtime.config import config
    
    adapter = PipecatAdapter(config)
    
    with (
        patch("app.realtime.providers.stt.deepgram.STTProviderConfig.create_deepgram_service", return_value="fallback-stt"),
        patch("app.realtime.providers.llm.groq.LLMProviderConfig.create_groq_service", return_value="llm"),
        patch("app.realtime.providers.tts.cartesia.TTSProviderConfig.create_cartesia_service", return_value="fallback-tts"),
        patch("app.realtime.providers.stt.sarvam.SarvamSTTProviderConfig.create_sarvam_service", return_value="stt"),
        patch("app.realtime.providers.tts.sarvam.SarvamTTSProviderConfig.create_sarvam_service", return_value="tts"),
    ):
        pipeline = adapter.create_pipeline()
    assert "stt" in pipeline
    assert "llm" in pipeline
    assert "tts" in pipeline
