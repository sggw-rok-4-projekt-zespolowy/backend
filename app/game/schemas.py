import uuid
from enum import StrEnum

from pydantic import BaseModel, Field

from app.track.schemas import TrackPrivate, TrackPublic


class GameSessionVariant(StrEnum):
    SINGLE = "SINGLE"
    DUEL = "DUEL"


class GameStatus(StrEnum):
    WAITING_FOR_PLAYERS = "WAITING"
    IN_PROGRESS = "PLAYING"
    FINISHED = "FINISHED"


class GameSessionInfoCreate(BaseModel):
    variant: GameSessionVariant = GameSessionVariant.SINGLE
    seconds_per_round: int = Field(ge=10, default=35)
    rounds: int = Field(ge=3, default=7)

class GameSessionInfoPublic(BaseModel):
    session_id: uuid.UUID
    variant: GameSessionVariant
    status: GameStatus
    players_ids: list[str]
    registered: bool
    seconds_per_round: int
    rounds: int

class PlayerMessage(BaseModel):
    answer: int


class ServerMessage(BaseModel):
    player_id: str
    matched_tracks: dict[str, list[dict[str,uuid.UUID]]]
    current_song_audio_url: str
    started: bool
    finished: bool
    tracks_data: list[TrackPublic]
    current_round_number: int
    game_session_metadata: GameSessionInfoPublic


class ServerMetaMessage(BaseModel):
    msg_type: str = "error"
    detail: str
