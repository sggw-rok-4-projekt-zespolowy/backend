from app.config import settings
from app.database import engine
from app.models.game_session import *
from app.models.message import *
from app.models.user import *
from app.models.track import *
from app.utils.helpers import create_admin
from sqlmodel import create_engine, select, Session, SQLModel

def initialize_database():
    # Create database tables if needed.
    SQLModel.metadata.create_all(engine)

    # Create admin if needed.
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == settings.ADMIN_USERNAME)).first()
    if not admin:
        create_admin()

if __name__ == "__main__":
    # To run standalone, go one level above app dir and run:
    # python -m app.initialize_database
    initialize_database()
