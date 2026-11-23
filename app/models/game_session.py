from app.models.player import Player
from app.models.round import Round
from app.models.track import TrackPublic
from asyncio import Task
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, func
from sqlmodel import JSON, Column, Field, SQLModel
from uuid import uuid4


class GameSessionVariant(StrEnum):
    SINGLE = "SINGLE"
    DUEL = "DUEL"


class GameSessionState(StrEnum):
    FINISHED = "FINISHED"
    IN_PROGRESS = "PLAYING"
    PLAYER_DISCONNECTION = "PLAYER_DISCONNECTION"
    TIMED_OUT = "TIMED_OUT"
    WAITING_FOR_PLAYERS = "WAITING"


class BaseGameSessionInfo(SQLModel):
    players_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    registered: bool = Field(default=False)
    rounds: int = Field(ge=3, default=7)
    state: GameSessionState = Field(default=GameSessionState.WAITING_FOR_PLAYERS)
    seconds_per_round: int = Field(ge=5, default=35)
    variant: GameSessionVariant = Field(default=GameSessionVariant.SINGLE)


class GameSessionInfo(BaseGameSessionInfo, table=True):
    session_id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class GameSessionInfoCreate(BaseGameSessionInfo):
    pass


class GameSessionInfoPublic(BaseGameSessionInfo):
    session_id: str


class InitializedGameSession(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    game_session_info: GameSessionInfo
    round_timer: Task | None = None
    connected_players: dict[str, Player] = {}
    disconnected_players: dict[str, Player] = {}
    all_players_answered: bool = False
    current_round: Round = Round()
    previous_tracks: list[TrackPublic] = []
    game_loop_running: bool = False
    disconnect_timeout_end_time: datetime | None = None
