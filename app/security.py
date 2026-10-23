"""Security and password hashing utilities.

Provides secure, modern bcrypt-based password hashing and verification
without dependency on passlib, avoiding the 72-byte limit bug when
initializing passlib backends against modern versions of bcrypt.
"""

import datetime
import os
from typing import Optional, Union
import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
INSECURE_DEFAULT_SECRET = "a_very_secret_key_for_sessions"



def is_production_environment() -> bool:
    """Check if the application is running in a production environment."""
    return bool(
        os.getenv("VERCEL")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("ENVIRONMENT", "").strip().lower() in ("production", "prod")
    )


def get_auth_cookie_config(max_age: Optional[int] = 30 * 24 * 3600) -> dict:
    """Return secure authentication cookie parameters.

    In production environments (HTTPS), secure=True is enforced.
    httponly=True and samesite='lax' are always enforced.
    """
    config = {
        "httponly": True,
        "samesite": "lax",
        "secure": is_production_environment(),
    }
    if max_age is not None:
        config["max_age"] = max_age
    return config


def get_jwt_secret_key() -> str:
    """Return the JWT signing secret key configured in the environment.

    In production environments, raises RuntimeError if SECRET_KEY is missing,
    empty, or set to the known insecure default value.
    """
    secret = os.getenv("SECRET_KEY", "").strip()
    if is_production_environment():
        if not secret or secret == INSECURE_DEFAULT_SECRET:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY must be set to a secure, "
                "cryptographically random secret in production environments."
            )
        return secret
    # Development/testing fallback
    return secret or INSECURE_DEFAULT_SECRET


JWT_SECRET_KEY = get_jwt_secret_key()


def create_access_token(
    user_id: Union[str, int],
    expires_delta: Optional[datetime.timedelta] = None,
) -> str:
    """Create a cryptographically signed JWT access token containing the user ID subject."""
    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta if expires_delta is not None else datetime.timedelta(days=30)
    )
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: Optional[str]) -> Optional[str]:
    """Validate and decode a JWT access token.

    Returns the subject (user_id as string) if the token is valid, properly signed,
    and not expired. Returns None for any invalid, expired, tampered, empty, or
    non-JWT token. Never accepts raw numeric IDs or unverified payloads.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        secret = get_jwt_secret_key()
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"], "verify_exp": True, "verify_signature": True},
        )
        sub = payload.get("sub")
        if sub is None:
            return None
        sub_str = str(sub).strip()
        if not sub_str:
            return None
        return sub_str
    except Exception:
        return None



def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Safely truncates input to 72 bytes to respect bcrypt's hard limit
    and avoid ValueError in bcrypt >= 4.0.0.
    """
    if isinstance(password, str):
        pwd_bytes = password.encode("utf-8")[:72]
    else:
        pwd_bytes = bytes(password)[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: Union[str, bytes]) -> bool:
    """Verify a plain password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        if isinstance(plain_password, str):
            pwd_bytes = plain_password.encode("utf-8")[:72]
        else:
            pwd_bytes = bytes(plain_password)[:72]

        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode("utf-8")
        else:
            hashed_bytes = hashed_password

        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


class _BcryptPasswordContext:
    """Passlib CryptContext drop-in replacement to avoid passlib+bcrypt incompatibilities."""

    def hash(self, secret: str) -> str:
        return get_password_hash(secret)

    def verify(self, secret: str, hash: str) -> bool:
        return verify_password(secret, hash)


pwd_context = _BcryptPasswordContext()
