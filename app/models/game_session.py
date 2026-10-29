from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, func
from sqlmodel import JSON, Column, Field, SQLModel
from uuid import UUID, uuid4


class GameSessionVariant(StrEnum):
    SINGLE = "SINGLE"
    DUEL = "DUEL"


class GameSessionStatus(StrEnum):
    WAITING_FOR_PLAYERS = "WAITING"
    IN_PROGRESS = "PLAYING"
    FINISHED = "FINISHED"


class BaseGameSessionInfo(SQLModel):
    players_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    registered: bool = Field(default=False)
    rounds: int = Field(ge=3, default=7)
    status: GameSessionStatus = Field(default=GameSessionStatus.WAITING_FOR_PLAYERS)
    seconds_per_round: int = Field(ge=10, default=35)
    variant: GameSessionVariant = Field(default=GameSessionVariant.SINGLE)


class GameSessionInfo(BaseGameSessionInfo, table=True):
    session_id: UUID = Field(primary_key=True, default_factory=uuid4)

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=False), server_default=func.now()),
    )


class GameSessionInfoCreate(BaseGameSessionInfo):
    pass


class GameSessionInfoPublic(BaseGameSessionInfo):
    session_id: UUID
