import os
from typing import Optional

# Sanitize Sarvam API exceptions to prevent secret leakage
try:
    from sarvamai.core.api_error import ApiError
    original_str = ApiError.__str__
    
    def safe_str(self) -> str:
        safe_headers = dict(self.headers) if self.headers else None
        if safe_headers and "api-subscription-key" in safe_headers:
            safe_headers["api-subscription-key"] = "***HIDDEN***"
        return f"headers: {safe_headers}, status_code: {self.status_code}, body: {self.body}"
        
    ApiError.__str__ = safe_str
except ImportError:
    pass

class RealtimeConfig:
    """Central configuration for the real-time conversational agent."""
    
    @property
    def deepgram_api_key(self) -> Optional[str]:
        return os.getenv("DEEPGRAM_API_KEY")

    @property
    def groq_api_key(self) -> Optional[str]:
        return os.getenv("GROQ_API_KEY")

    @property
    def sarvam_api_key(self) -> str:
        key = os.getenv("SARVAM_API_KEY")
        if not key:
            raise RuntimeError(
                "SARVAM_API_KEY is missing. Configure it before starting the voice pipeline."
            )
        key = key.strip()
        if not key:
            raise RuntimeError("SARVAM_API_KEY is empty.")
        return key

        
    @property
    def cartesia_api_key(self) -> Optional[str]:
        return os.getenv("CARTESIA_API_KEY")
        
    @property
    def cartesia_voice_id(self) -> str:
        # Default to Arushi voice if not explicitly provided
        return os.getenv("CARTESIA_VOICE_ID", "95d51f79-c397-46f9-b49a-23763d3eaa2d")

    @property
    def sarvam_voice_id(self) -> str:
        return os.getenv("SARVAM_VOICE_ID", "anushka")

        
    @property
    def public_base_url(self) -> Optional[str]:
        return os.getenv("PUBLIC_BASE_URL")

config = RealtimeConfig()
