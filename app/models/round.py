from app.models.track import TrackPublic
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel


class RoundState(StrEnum):
    INITIAL_ROUND = "INITIAL_ROUND"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"

class Round(BaseModel):
    state: RoundState = RoundState.INITIAL_ROUND
    number: int = 1
    correct_answer: int | None = None
    track: TrackPublic | None = None
    end_time: datetime | None = None


