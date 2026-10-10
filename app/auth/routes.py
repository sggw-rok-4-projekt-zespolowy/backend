from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import settings
from ..database import get_db
from ..shared.dependencies import get_current_active_user, get_refresh_token_from_cookie
from .models import User
from .schemas import (
    AuthResponse,
    MessageResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from .services import login_user, logout_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    """Set refresh token as HTTP-only, Secure, SameSite cookie."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS
        * 24
        * 60
        * 60,  # Convert days to seconds
        path="/",
    )


def clear_refresh_token_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserRegister,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """
    Register a new user.

    Returns user info and access token. Sets refresh token as HTTP-only cookie.
    """
    user, access_token, refresh_token = await register_user(db, user_data)
    set_refresh_token_cookie(response, refresh_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    login_data: UserLogin,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """
    Authenticate user with email and password.

    Returns user info and access token. Sets refresh token as HTTP-only cookie.
    """
    user, access_token, refresh_token = await login_user(db, login_data)
    set_refresh_token_cookie(response, refresh_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Logout current user.

    Invalidates the refresh token and clears the cookie.
    """
    await logout_user(db, current_user)
    clear_refresh_token_cookie(response)

    return MessageResponse(message="Successfully logged out")


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """
    Refresh access token using the refresh token from cookie.

    Returns user info and new access token.
    """
    refresh_token = get_refresh_token_from_cookie(request)
    user, access_token = await refresh_tokens(db, refresh_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """
    Get current authenticated user info.

    Requires valid access token in Authorization header.
    """
    return UserResponse.model_validate(current_user)
