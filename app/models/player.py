from app.models.track import TrackPublic
from enum import StrEnum
from pydantic import BaseModel, ConfigDict
from starlette.websockets import WebSocket

class PlayerState(StrEnum):
    ANSWERING = "ANSWERING"
    ANSWERED = "ANSWERED"

class Player(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: PlayerState = PlayerState.ANSWERING
    matched_tracks: list[TrackPublic] = []
    number_of_guesses: int = 0
    correct_answers: int = 0
    answer: int | None = None
    websocket: WebSocket

