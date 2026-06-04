import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

class UserCache:
    """
    Utility for caching user status and session data in Redis.
    """
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self.is_available = True
        except Exception as e:
            print(f"REDIS ERROR (UserCache): Connection failed. {e}")
            self.is_available = False

    def get_user_status(self, user_id: int) -> dict:
        """Retrieves cached status for a user."""
        if not self.is_available:
            return None
        
        try:
            data = self.client.get(f"user_status:{user_id}")
            return json.loads(data) if data else None
        except Exception as e:
            print(f"REDIS USER GET ERROR: {e}")
            return None

    def set_user_status(self, user_id: int, status_data: dict, ttl: int = 3600):
        """Caches user status (default TTL 1h)."""
        if not self.is_available:
            return
        
        try:
            self.client.setex(f"user_status:{user_id}", ttl, json.dumps(status_data))
        except Exception as e:
            print(f"REDIS USER SET ERROR: {e}")

    def get_user(self, user_id: int) -> dict:
        """Retrieves full user data (dict) from cache."""
        if not self.is_available:
            return None
        try:
            data = self.client.get(f"user_data:{user_id}")
            return json.loads(data) if data else None
        except Exception:
            return None

    def set_user(self, user_id: int, user_data: dict, ttl: int = 3600):
        """Caches full user data (dict)."""
        if not self.is_available:
            return
        # Remove potentially huge or sensitive relations if any
        user_data.pop("_sa_instance_state", None)
        try:
            self.client.setex(f"user_data:{user_id}", ttl, json.dumps(user_data))
        except Exception:
            pass

    def invalidate_user(self, user_id: int):
        """Removes user from cache."""
        if not self.is_available:
            return
        try:
            self.client.delete(f"user_status:{user_id}")
            self.client.delete(f"user_data:{user_id}")
        except Exception as e:
            print(f"REDIS USER DELETE ERROR: {e}")

# Global instance
user_cache = UserCache()
