from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth.models import User
from ..auth.utils import verify_access_token
from ..database import get_db
from .exceptions import (
    InactiveUserException,
    InvalidTokenException,
    UserNotFoundException,
)

# OAuth2 scheme - extracts token from Authorization: Bearer <token> header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Dependency to get the current authenticated user from the access token.
    Used with OAuth2PasswordBearer for automatic token extraction.
    """
    user_id = verify_access_token(token)
    if user_id is None:
        raise InvalidTokenException()

    result = await db.exec(select(User).where(User.id == user_id))
    user = result.one_or_none()

    if user is None:
        raise UserNotFoundException()

    if not user.is_active:
        raise InactiveUserException()

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency to ensure user is active (alias for clarity)."""
    return current_user


def get_refresh_token_from_cookie(request: Request) -> str:
    """Extract refresh token from HTTP-only cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise InvalidTokenException("Refresh token not found")
    return refresh_token
