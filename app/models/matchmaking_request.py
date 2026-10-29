from app.models.game_session import GameSessionInfo, GameSessionInfoCreate
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class MatchmakingRequest(BaseModel):
    requestOwnerId: int
    requestedGameSessionInfo: GameSessionInfoCreate
    createdGameSessionInfo: GameSessionInfo | None
    matchedRequest: MatchmakingRequest | None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    fulfilled: bool
