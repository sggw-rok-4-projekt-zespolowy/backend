import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from ..config import settings

# Initialize pwdlib password hasher with Argon2
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using Argon2 (via pwdlib)."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2 hash."""
    return password_hash.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """Create a SHA256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int) -> str:
    """Create a short-lived access token (15 min by default)."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived refresh token (7 days by default)."""
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict[str, object] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_access_token(token: str) -> int | None:
    """Verify an access token and return the user_id if valid."""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "access":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def verify_refresh_token(token: str) -> int | None:
    """Verify a refresh token and return the user_id if valid."""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "refresh":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None
