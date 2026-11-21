from app.models.game_session import GameSessionInfoPublic
from app.models.track import TrackPublic
from pydantic import BaseModel
from typing import Literal
from uuid import UUID


class PlayerMessage(BaseModel):
    answer: int


class ServerMessage(BaseModel):
    player_id: str
    matched_tracks: dict[str, list[TrackPublic]]
    current_song_audio_url: str
    started: bool
    finished: bool
    tracks_data: list[TrackPublic]
    current_round_number: int
    game_session_metadata: GameSessionInfoPublic


class ServerMetaMessage(BaseModel):
    msg_type: Literal["error", "info"] = "error"
    detail: str
