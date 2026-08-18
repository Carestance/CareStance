import pytest
import sys
from unittest.mock import MagicMock

# Mock pipecat module so we can test the configs without it installed
mock_pipecat = MagicMock()
mock_pipecat.services.deepgram.DeepgramSTTService = MagicMock()
mock_pipecat.services.groq.GroqLLMService = MagicMock()
mock_pipecat.services.cartesia.CartesiaTTSService = MagicMock()
sys.modules['pipecat'] = mock_pipecat
sys.modules['pipecat.services'] = mock_pipecat.services
sys.modules['pipecat.services.deepgram'] = mock_pipecat.services.deepgram
sys.modules['pipecat.services.groq'] = mock_pipecat.services.groq
sys.modules['pipecat.services.cartesia'] = mock_pipecat.services.cartesia

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
    
    # We must provide mock keys for the environment if missing
    import os
    os.environ["DEEPGRAM_API_KEY"] = "mock"
    os.environ["GROQ_API_KEY"] = "mock"
    os.environ["CARTESIA_API_KEY"] = "mock"
    
    pipeline = adapter.create_pipeline()
    assert "stt" in pipeline
    assert "llm" in pipeline
    assert "tts" in pipeline
