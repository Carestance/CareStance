from typing import Optional
from app.realtime.config import config

class LLMProviderConfig:
    @staticmethod
    def create_groq_service(api_key: Optional[str] = None):
        try:
            from pipecat.services.groq.llm import GroqLLMService
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")
            
        key = api_key or config.groq_api_key
        if not key:
            raise ValueError("Groq API key not provided or found in environment.")
            
        return GroqLLMService(
            api_key=key,
            settings=GroqLLMService.Settings(model="llama-3.1-8b-instant")
        )
