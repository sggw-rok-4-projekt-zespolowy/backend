from app.config import settings
from fastapi import Depends
from sqlmodel import create_engine, Session, SQLModel
from typing import Annotated, Generator


engine = create_engine(settings.DATABASE_URL)


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
