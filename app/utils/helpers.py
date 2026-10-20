from app.config import settings
from app.database import engine
from app.models.user import USER_ROLE
from app.utils.crud import create_user
from sqlmodel import Session

def create_admin():
    with Session(engine) as session:
        create_user(
            session,
            settings.ADMIN_EMAIL,
            settings.ADMIN_USERNAME,
            settings.ADMIN_PASSWORD,
            role=USER_ROLE.ADMIN
        )

