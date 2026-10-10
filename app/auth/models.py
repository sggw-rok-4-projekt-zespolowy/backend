from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model for authentication."""

    __tablename__: str = "users"  #  type: ignore

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    username: str = Field(unique=True, index=True, min_length=6, max_length=20)
    hashed_password: str = Field(max_length=255)
    score: int = Field(ge=0, default=0)

    is_active: bool = Field(default=True)

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        ),
    )

    refresh_token_hash: str | None = Field(default=None, max_length=255)
