from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# Request schemas
class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(...)


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    username: str = Field(..., min_length=6, max_length=20)


# Response schemas
class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime | None = None
    score: int

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str


class MessageResponse(BaseModel):
    message: str


# Token schemas
class TokenPayload(BaseModel):
    sub: str  # user_id as string
    type: str  # "access" or "refresh"
    exp: datetime | None = None
