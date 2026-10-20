from app.config import settings
from app.database import SessionDep
from app.models.user import User, USER_ROLE
from app.utils.crud import read_user_by_username
from app.utils.exceptions import HTTPUnauthorized, HTTPForbidden
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import decode, encode, InvalidTokenError
from typing import Annotated


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def jwt_encode(
        data: dict,
):
    current_time = datetime.now(timezone(timedelta(), 'UTC'))
    exp_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    data.update({"exp": current_time + exp_delta})
    return encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def jwt_decode(token: str):
    return decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": True, "require": ["exp"]}
    )

def get_current_user(
        allowed_roles: list[USER_ROLE] | None = [],
        enforce_active = False
    ):
    def dependency(
        token: Annotated[str, Depends(oauth2_scheme)],
        session: SessionDep
    ) -> User:

        try:
            payload = jwt_decode(token)
            if not "sub" in payload:
                raise HTTPUnauthorized
        except InvalidTokenError:
            raise HTTPUnauthorized

        user = read_user_by_username(session, username=payload["sub"])

        if not user:
            raise HTTPUnauthorized

        if enforce_active and not user.is_active:
            raise HTTPUnauthorized

        if allowed_roles:
            if (
                USER_ROLE.REGULAR_USER in allowed_roles and
                user.role not in [
                        USER_ROLE.ADMIN,
                        USER_ROLE.REGULAR_USER
                ]
            ) or (
                USER_ROLE.ADMIN in allowed_roles and
                user.role != USER_ROLE.ADMIN
            ):
                raise HTTPForbidden

        return user
    return dependency



def allowed_roles(allowed_roles: list[USER_ROLE]):
    authorization_exception = HTTPException(status_code=401, detail="Not authorized")

    def check_role(current_user: Annotated[User, Depends(get_current_user)]):
        if current_user.role not in allowed_roles:
            raise authorization_exception

    return check_role
