from app.utils.cryptography import hash_password
from app.models.user import User, USER_ROLE, UserCreate
from app.models.game_session import GameSessionInfo
from app.models.track import Track
from sqlmodel import select, Session

# Users

def create_user(
    session: Session, email: str, username: str, password: str, role: USER_ROLE
) -> User:
    new_user = User(
        email=email, username=username, password=hash_password(password), role=role
    )

    session.add(new_user)
    session.commit()

    new_user_in_db = read_user_by_username(session, username)
    assert new_user_in_db != None

    return new_user_in_db


def read_user_by_username(session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def read_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def read_user_by_id(session: Session, id: int) -> User | None:
    return session.exec(select(User).where(User.id == id)).first()

# GameSessionInfo

def create_game_session_info(
    session: Session, game_session_info: GameSessionInfo
) -> GameSessionInfo:

    session.add(game_session_info)
    session.commit()
    session.refresh(game_session_info)
    return game_session_info

def read_game_session_info_by_game_session_id(
    session: Session, game_session_id: str
) -> GameSessionInfo | None:

    return session.get(GameSessionInfo, game_session_id)

def update_game_session_info(
    session: Session, game_session_info: GameSessionInfo
) -> GameSessionInfo:

    session.add(game_session_info)
    session.commit()
    session.refresh(game_session_info)
    return game_session_info

# Track

def read_track_by_deezer_id(session: Session, deezer_id: str):
    return session.exec(select(Track).where(Track.deezer_track_id == deezer_id)).first()

def delete_track_by_deezer_id(session: Session, deezer_id: str):
    track = read_track_by_deezer_id(session, deezer_id)
    session.delete(track)
    session.commit()

