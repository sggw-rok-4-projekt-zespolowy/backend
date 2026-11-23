from enum import Enum
from sqlmodel import Field, SQLModel
from uuid import uuid4


class USER_ROLE(Enum):
    ADMIN = "ADMIN"
    REGULAR_USER = "REGULAR_USER"


class BaseUser(SQLModel):
    # Auth related
    email: str = Field(unique=True, max_length=255)
    is_active: bool = Field(default=True)
    role: USER_ROLE = Field(default=USER_ROLE.REGULAR_USER)
    username: str = Field(unique=True, min_length=6, max_length=255)

    # Additional
    score: int = Field(ge=0, default=0)


class User(BaseUser, table=True):
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    password: str = Field(max_length=255)


class UserCreate(BaseUser):
    password: str


class UserPublic(BaseUser):
    id: str
