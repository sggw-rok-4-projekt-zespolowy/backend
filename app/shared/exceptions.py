from fastapi import HTTPException, status


class AuthException(HTTPException):
    """Base authentication exception."""

    pass


class InvalidCredentialsException(AuthException):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidTokenException(AuthException):
    """Raised when a token is invalid or expired."""

    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserExistsException(AuthException):
    """Raised when trying to register with existing email/username."""

    def __init__(self, field: str = "email"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with this {field} already exists",
        )


class UserNotFoundException(AuthException):
    """Raised when user is not found."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


class InactiveUserException(AuthException):
    """Raised when user account is inactive."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
