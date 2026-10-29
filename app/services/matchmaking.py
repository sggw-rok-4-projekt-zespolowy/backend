from app.database import engine
from app.models.game_session import GameSessionInfo, GameSessionInfoCreate, GameSessionStatus, GameSessionVariant
from app.models.matchmaking_request import MatchmakingRequest
from app.models.user import User
from app.utils.logger import logger
from datetime import datetime, timedelta, timezone
from sqlmodel import select, Session


class MatchmakingService:
    def __init__(self):
        self.requests: dict[int, MatchmakingRequest] = {}


    def createRequest(self, requestOwnerId: int, requestedGameSessionInfo: GameSessionInfoCreate) -> MatchmakingRequest:
        # Create and store MatchmakingRequest
        request = MatchmakingRequest(
                requestOwnerId = requestOwnerId,
                requestedGameSessionInfo = requestedGameSessionInfo,
                createdGameSessionInfo = None,
                matchedRequest = None,
                fulfilled = False
            )

        if requestOwnerId in self.requests:
            raise ValueError('User already has an awaiting MatchmakingRequest')

        self.requests[requestOwnerId] = request

        return request


    def deleteRequest(self, matchmakingRequest: MatchmakingRequest):

        # Removes a paired GameSessionInfo if it was created
        if matchmakingRequest.fulfilled:
            with Session(engine) as session:
                session.delete(matchmakingRequest.createdGameSessionInfo)
                session.commit()

        # Removes the MatchmakingRequest
        del self.requests[ matchmakingRequest.requestOwnerId ]

        # Checks if there was a paired MatchmakingRequest and removes it, if not yet removed.
        if (
                matchmakingRequest.matchedRequest != None and
                matchmakingRequest.matchedRequest.requestOwnerId in self.requests
        ):
            self.deleteRequest(matchmakingRequest.matchedRequest)



    def findRequestByOwner(self, requestOwnerId: int) -> MatchmakingRequest | None:
        # Find and return stored MatchmakingRequest by requestOwnerId
        if requestOwnerId in self.requests:
            return self.requests[requestOwnerId]
        else:
            return None


    def findRequestsByGameSessionInfo(self, requestedGameSessionInfo: GameSessionInfoCreate) -> list[MatchmakingRequest]:
        # Find and return stored MatchmakingRequest by GameSessionInfo
        foundRequests = filter(
                lambda x:
                    x.requestedGameSessionInfo.rounds == requestedGameSessionInfo.rounds and
                    x.requestedGameSessionInfo.seconds_per_round == requestedGameSessionInfo.seconds_per_round and
                    x.requestedGameSessionInfo.variant == requestedGameSessionInfo.variant,
                list(self.requests.values())
            )

        return list(foundRequests)


    def fulfillRequest(self, matchmakingRequest: MatchmakingRequest) -> bool:
        # Returns True if request was fulfilled, False otherwise.

        # This request was already fulfilled, no need to process it again.
        if matchmakingRequest.fulfilled:
            return True

        match matchmakingRequest.requestedGameSessionInfo.variant:

            case GameSessionVariant.SINGLE:
                requestedGameSessionInfo = matchmakingRequest.requestedGameSessionInfo
                gameSessionInfo = GameSessionInfo.model_validate(
                        {
                            **requestedGameSessionInfo.model_dump(),
                            "players_ids": [
                                matchmakingRequest.requestOwnerId,
                            ]
                        }
                    )

                with Session(engine) as session:
                    session.add(gameSessionInfo)
                    session.commit()
                    session.refresh(gameSessionInfo)

                matchmakingRequest.fulfilled = True
                matchmakingRequest.createdGameSessionInfo = gameSessionInfo

                return True

            case GameSessionVariant.DUEL:
                # Match the given request with another of the same type, from another user.
                requestsOfThisKind = self.findRequestsByGameSessionInfo(
                        matchmakingRequest.requestedGameSessionInfo
                    )

                # Filter out own request, and fulfilled ones
                otherRequestsOfThisKind = list(filter(
                        lambda x: x.requestOwnerId != matchmakingRequest.requestOwnerId and x.fulfilled == False,
                        requestsOfThisKind
                    ))

                if len(otherRequestsOfThisKind) > 0:
                    otherRequestsOfThisKind.sort(key=lambda x: x.createdAt) # Sorting by creation time, to get the longest waiting request.
                    matchedRequest = otherRequestsOfThisKind[0]
                    requestedGameSessionInfo = matchedRequest.requestedGameSessionInfo

                    gameSessionInfo = GameSessionInfo.model_validate(
                            {
                                **requestedGameSessionInfo.model_dump(),
                                "players_ids": [
                                    matchmakingRequest.requestOwnerId,
                                    matchedRequest.requestOwnerId
                                ]
                            }
                        )

                    with Session(engine) as session:
                        session.add(gameSessionInfo)
                        session.commit()
                        session.refresh(gameSessionInfo)


                    matchmakingRequest.createdGameSessionInfo = gameSessionInfo
                    matchmakingRequest.matchedRequest = otherRequestsOfThisKind[0]
                    matchmakingRequest.fulfilled = True
                    otherRequestsOfThisKind[0].createdGameSessionInfo = gameSessionInfo
                    otherRequestsOfThisKind[0].matchedRequest = matchmakingRequest
                    otherRequestsOfThisKind[0].fulfilled = True

                    return True

            case _:

                raise ValueError("Unrecognized GameSessionVariant")

        return False


    def isRequestStale(self, matchmakingRequest: MatchmakingRequest, timeLimit: timedelta) -> bool:

        # Refreshing the paired GameSessionInfo, as it could've been finished in the meantime.
        if (
                matchmakingRequest.fulfilled and
                matchmakingRequest.createdGameSessionInfo
        ):
            # TODO: Get the copy from DB then refresh it and pair with the request again
            with Session(engine) as session:
                gameSessionInfo = session.exec(
                        select(GameSessionInfo).where(
                            GameSessionInfo.session_id == matchmakingRequest.createdGameSessionInfo.session_id
                        )
                    ).first()
                session.refresh(gameSessionInfo)
                matchmakingRequest.createdGameSessionInfo = gameSessionInfo

        if (
                matchmakingRequest.fulfilled and
                matchmakingRequest.createdGameSessionInfo and (
                    (
                        matchmakingRequest.createdGameSessionInfo.status == GameSessionStatus.WAITING_FOR_PLAYERS and
                        matchmakingRequest.createdGameSessionInfo.created_at and
                        datetime.utcnow() - matchmakingRequest.createdGameSessionInfo.created_at > timeLimit
                    ) or (
                        matchmakingRequest.createdGameSessionInfo.status == GameSessionStatus.FINISHED
                    )
                )
        ):
            return True
        else:
            return False


    def removeStaleRequests(self):
        # Cleanup of old, not fulfilled requests
        # TODO
        pass

matchmakingService = MatchmakingService()
