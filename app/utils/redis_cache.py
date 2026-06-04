import redis
import hashlib
import json
import os
from dotenv import load_dotenv

load_dotenv()

class RedisCache:
    """
    A simple Redis cache utility for AI responses with an in-memory fallback.
    """
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.local_cache = {}  # Local fallback dictionary
        try:
            # Add timeouts to prevent hanging the event loop on remote connection failures
            self.client = redis.from_url(
                self.redis_url, 
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                retry_on_timeout=True
            )
            self.client.ping()
            self.is_available = True
        except Exception as e:
            print(f"REDIS ERROR: Connection failed. {e}. Using local in-memory fallback.")
            self.is_available = False

    def _get_hash(self, text: str) -> str:
        """Generates a SHA-256 hash of the input text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get(self, prompt: str) -> str:
        """Retrieves cached content for a prompt."""
        key = self._get_hash(prompt)
        
        # Check local fallback first
        if key in self.local_cache:
            return self.local_cache[key]
            
        if not self.is_available:
            return None
        
        try:
            redis_key = f"ai_cache:{key}"
            val = self.client.get(redis_key)
            if val:
                self.local_cache[key] = val  # Sync to local copy
            return val
        except Exception as e:
            self.is_available = False  # Mark unavailable on failure to prevent console spam
            return None

    def set(self, prompt: str, response: str, ttl: int = 86400):
        """Caches a response for a prompt (default TTL 24h)."""
        key = self._get_hash(prompt)
        self.local_cache[key] = response  # Keep local copy
        
        if not self.is_available:
            return
        
        try:
            redis_key = f"ai_cache:{key}"
            self.client.setex(redis_key, ttl, response)
        except Exception as e:
            self.is_available = False  # Mark unavailable on failure to prevent console spam

# Global instance
ai_cache = RedisCache()
