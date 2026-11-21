from asyncio import create_task
from app.config import settings
from app.database import SessionDep
from app.models.game_session import (
    GameSessionInfo,
    GameSessionInfoCreate,
    GameSessionInfoPublic,
    GameSessionState,
    GameSessionVariant,
)
from app.models.message import PlayerMessage, ServerMetaMessage
from app.models.player import PlayerState
from app.models.round import RoundState
from app.models.user import User
from app.services.game import manager, game_sessions_loader
from app.services.matchmaking import matchmakingService
from app.utils.dependencies import get_current_user
from app.utils.logger import logger
from collections.abc import Sequence
from datetime import timedelta
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from random import randint
from sqlmodel import select, func
from threading import Timer
from time import sleep
from typing import Annotated
from uuid import UUID, uuid4

router = APIRouter(prefix="/game")


@router.get("", response_model=Sequence[GameSessionInfoPublic])
async def read_sessions(session: SessionDep) -> Sequence[GameSessionInfo]:
    sessions = session.exec(select(GameSessionInfo)).all()
    return sessions


@router.post("/quick-start", response_model=GameSessionInfoPublic)
async def create_session(
    session: SessionDep, requested_session: GameSessionInfoCreate
) -> GameSessionInfo:
    player_count = 1 if requested_session.variant == GameSessionVariant.SINGLE else 2
    sleep(3)
    new_game_session = GameSessionInfo(
        variant=requested_session.variant,
        players_ids=[str(randint(1,99999)) for _ in range(player_count)],
    )

    session.add(new_game_session)
    session.commit()
    session.refresh(new_game_session)
    return new_game_session


# This dict holds lists of players waiting for a session with specific settings
awaiting_players_queue: dict[str, list[int]] = {}  # TODO - Move this elsewhere


@router.post("/registered-start", response_model=GameSessionInfoPublic)
async def create_registered_session(
    session: SessionDep,
    requestedGameSession: GameSessionInfoCreate,
    currentUser: Annotated[User, Depends(get_current_user(enforce_active=True))],
) -> GameSessionInfo | Response:
    logger.info(
        f"[registered start] Received matchmaking request for session: {requestedGameSession}"
    )

    #Pyright thinks user id can be None here, but it can't.
    #Here to make it happy.
    assert currentUser.id != None

    # Means: this game session info object is for registered players
    requestedGameSession.registered = True

    # Housekeeping: Removing stale requests
    matchmakingService.removeStaleRequests()

    matchmakingRequest = matchmakingService.findRequestByOwner(currentUser.id)

    if not matchmakingRequest:
        matchmakingRequest = matchmakingService.createRequest(currentUser.id, requestedGameSession)

    # Trying to match with another player, or creating single player session.
    matchmakingService.fulfillRequest(matchmakingRequest)

    if (
            matchmakingRequest and
            matchmakingRequest.createdGameSessionInfo and
            matchmakingRequest.fulfilled
    ):
        return matchmakingRequest.createdGameSessionInfo
    else:
        return Response(
            status_code=202,
            content="Waiting for another player"
        )


@router.websocket("/{game_session_id}/{player_id}")
async def game_session_ws(
    db_session: SessionDep,
    websocket: WebSocket,
    game_session_id: str,
    player_id: str,
    access_token: str = "",
) -> None:

    # Initial connection request handling
    await websocket.accept()
    await manager.acknowledgeConnectionRequest(websocket, game_session_id)

    errorMessage = await manager.validateConnectionRequest(websocket, db_session, game_session_id, player_id, access_token)

    if errorMessage:
        await manager.sendErrorMessage(websocket, game_session_id, errorMessage)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.acknowledgeValidConnectionRequest(websocket, game_session_id, player_id)
    # END: Initial connection request handling

    try:
        try:

            # Game Session initialization handling
            if not manager.isGameSessionInitialized(game_session_id):
                manager.initializeGameSession(db_session, game_session_id)

            await manager.acknowledgeGameSessionInitialized(websocket, game_session_id)
            # END: Game Session initailization handling

            # Player connection/reconnection handling
            await manager.connectPlayer(websocket, game_session_id, player_id)
            # Player state can differ depending on if they first connect or if they reconnect
            manager.decidePlayerState(game_session_id, player_id)
            await manager.acknowledgePlayerState(websocket, game_session_id, player_id)
            # END: Player connection/reconnection handling

            # Manage game logic loop
            await manager.decideGameState(game_session_id)

            if not manager.isGameLoopRunning(game_session_id):
                # Will start an asynchronous game loop
                create_task(manager.runGameLoop(game_session_id))
            # END: Manage game logic loop

            # Player input loop
            while manager.keepPlayersConnected(game_session_id):

                player_message = await websocket.receive_text()
                await manager.acknowledgePlayerMessage(websocket, game_session_id, player_message)

                if manager.getRoundState(game_session_id) == RoundState.IN_PROGRESS:
                    if manager.getPlayerState(game_session_id, player_id) == PlayerState.ANSWERING:

                        errorMessage = await manager.validatePlayerMessage(websocket, game_session_id, player_message)

                        if not errorMessage:
                            # Take player message
                            await manager.acknowledgeValidPlayerGuess(websocket, game_session_id)
                            manager.processPlayerGuess(game_session_id, player_id, player_message)
                            manager.setPlayerState(game_session_id, player_id, PlayerState.ANSWERED)

                        else:
                            await manager.sendErrorMessage(websocket, game_session_id, errorMessage)


                    else:
                        # Discard player message
                        await manager.answerAlreadyGivenMessage(websocket, game_session_id)

                else:
                    # Discard player message
                    await manager.roundNotInProgressMessage(websocket, game_session_id)
            # END: Player input loop


            # Normal disconnection handling
            await manager.disconnectPlayer(websocket, game_session_id, player_id)
            await websocket.close()
            return
            # END: Normal disconnection handling

        except WebSocketDisconnect:
            # Abnormal disconnection handling
            await manager.disconnectPlayer(websocket, game_session_id, player_id)
            return
            # END: Abnormal disconnection handling

    except RuntimeError as e:
        # This will occur on disconnect, due to asynchronous handling of WebSockets. It's safe to ignore.
        if str(e) == "Unexpected ASGI message 'websocket.send', after sending 'websocket.close' or response already completed.":
            return
        else:
            raise e
