from app.config import settings
from app.database import SessionDep
from app.models.user import User, USER_ROLE, UserCreate, UserPublic
from app.utils.crud import create_user, read_user_by_email, read_user_by_username
from app.utils.cryptography import verify_password
from app.utils.dependencies import oauth2_scheme, get_current_user, jwt_encode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from typing import Annotated


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def create(session: SessionDep, data: UserCreate) -> dict:

    # Only admin can create another admin.
    token = Depends(oauth2_scheme)
    if data.role == USER_ROLE.ADMIN:
        get_current_user(allowed_roles=[USER_ROLE.ADMIN])(token, session)

    # Creating user if credentials are unique
    try:
        new_user = create_user(
            session,
            email=data.email,
            username=data.username,
            password=data.password,
            role=data.role,
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400, detail="User with that email or username already exists"
        )

    # Returning user with access_token for instant login
    new_token = jwt_encode({"sub": new_user.username})
    return {"access_token": new_token, "token_type": "bearer", "user": new_user}


@router.post("/login")
def login(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> dict:
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid credentials"
    )

    # Username can be either e-mail or an actual username
    user = read_user_by_email(session, email=form_data.username)

    if not user:
        user = read_user_by_username(session, username=form_data.username)

    if not user:
        raise credentials_exception

    if not verify_password(form_data.password, user.password):
        raise credentials_exception

    token = jwt_encode({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserPublic)
def read_me(
    current_user: Annotated[User, Depends(get_current_user([USER_ROLE.REGULAR_USER]))],
):
    return current_user
