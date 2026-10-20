from app.utils.cryptography import hash_password
from app.models.user import User, USER_ROLE, UserCreate
from sqlmodel import select, Session


# Users

def create_user(session: Session, email: str, username: str, password: str, role: USER_ROLE) -> User:
    new_user = User(
        email = email,
        username = username,
        password = hash_password(password),
        role = role
    )

    session.add(new_user)
    session.commit()

    new_user_in_db = read_user_by_username(session, username)
    assert new_user_in_db != None

    return new_user_in_db

def read_user_by_username(session: Session, username: str) -> User | None:
    return session.exec(
            select(User).where(
                User.username == username
            )
        ).first()

def read_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(
            select(User).where(
                User.email == email
            )
        ).first()

def read_user_by_id(session: Session, id: int) -> User | None:
    return session.exec(
            select(User).where(
                User.id == id
            )
        ).first()
