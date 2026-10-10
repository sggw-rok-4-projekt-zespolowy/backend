from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..shared.exceptions import (
    InactiveUserException,
    InvalidCredentialsException,
    InvalidTokenException,
    UserExistsException,
    UserNotFoundException,
)
from .models import User
from .schemas import UserLogin, UserRegister
from .utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    verify_refresh_token,
)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get a user by email address."""
    result = await db.exec(select(User).where(User.email == email))
    return result.one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get a user by username."""
    result = await db.exec(select(User).where(User.username == username))
    return result.one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get a user by ID."""
    result = await db.exec(select(User).where(User.id == user_id))
    return result.one_or_none()


async def register_user(
    db: AsyncSession, user_data: UserRegister
) -> tuple[User, str, str]:
    """
    Register a new user.
    Returns: (user, access_token, refresh_token)
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise UserExistsException("email")

    # Check if username already exists
    existing_user = await get_user_by_username(db, user_data.username)
    if existing_user:
        raise UserExistsException("username")

    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens (user.id is guaranteed after commit)
    assert user.id is not None
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token hash
    user.refresh_token_hash = hash_token(refresh_token)
    await db.commit()

    return user, access_token, refresh_token


async def login_user(db: AsyncSession, login_data: UserLogin) -> tuple[User, str, str]:
    """
    Authenticate user and generate tokens.
    Returns: (user, access_token, refresh_token)
    """
    user = await get_user_by_email(db, login_data.email)

    if not user:
        raise InvalidCredentialsException()

    if not verify_password(login_data.password, user.hashed_password):
        raise InvalidCredentialsException()

    if not user.is_active:
        raise InactiveUserException()

    # Generate tokens
    assert user.id is not None
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token hash
    user.refresh_token_hash = hash_token(refresh_token)
    await db.commit()

    return user, access_token, refresh_token


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[User, str]:
    """
    Refresh access token using a valid refresh token.
    Returns: (user, new_access_token)
    """
    user_id = verify_refresh_token(refresh_token)
    if user_id is None:
        raise InvalidTokenException("Invalid or expired refresh token")

    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundException()

    if not user.is_active:
        raise InactiveUserException()

    # Verify refresh token hash matches
    if user.refresh_token_hash != hash_token(refresh_token):
        raise InvalidTokenException("Refresh token has been revoked")

    # Generate new access token
    assert user.id is not None
    access_token = create_access_token(user.id)

    return user, access_token


async def logout_user(db: AsyncSession, user: User) -> None:
    """Logout user by invalidating their refresh token."""
    user.refresh_token_hash = None
    await db.commit()
