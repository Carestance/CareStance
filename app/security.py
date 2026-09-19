"""Security and password hashing utilities.

Provides secure, modern bcrypt-based password hashing and verification
without dependency on passlib, avoiding the 72-byte limit bug when
initializing passlib backends against modern versions of bcrypt.
"""

from typing import Union
import bcrypt


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
