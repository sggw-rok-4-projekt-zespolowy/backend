import uuid

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlmodel import JSON, Column, Field, SQLModel

from .schemas import GameSessionVariant, GameStatus


class GameSessionInfo(SQLModel, table=True):
    __tablename__: str = "game_sessions"  #  type: ignore

    session_id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    variant: GameSessionVariant = Field(default=GameSessionVariant.SINGLE)
    status: GameStatus = Field(default=GameStatus.WAITING_FOR_PLAYERS)
    seconds_per_round: int = Field(ge=10, default=35)
    rounds: int = Field(ge=3, default=7)
    registered: bool = Field(default=False)
    players_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

