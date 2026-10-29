from asyncio import run
from app.config import settings
from app.database import SessionDep
from app.models.game_session import (
    GameSessionInfo,
    GameSessionInfoCreate,
    GameSessionInfoPublic,
    GameSessionStatus,
    GameSessionVariant,
)
from app.models.message import PlayerMessage, ServerMetaMessage
from app.models.user import User
from app.services.game import NoTracksError, manager, game_sessions_loader
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
        players_ids=[randint(1,99999) for _ in range(player_count)],
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

    matchmakingRequest = matchmakingService.findRequestByOwner(currentUser.id)

    # Housekeeping: Removing stale requests
    # TODO: In addition, a time-based trigger could be used, to remove stale in batches.
    if matchmakingRequest:
        if matchmakingService.isRequestStale(
                matchmakingRequest,
                timedelta(seconds=settings.STALE_MATCHMAKING_REQUEST_TIME)
            ):
            matchmakingService.deleteRequest(matchmakingRequest)
            matchmakingRequest = None

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
            status_code=202, content="Waiting for another player"
        )


@router.websocket("/{game_session_id}/{player_id}")
async def game_session_ws(
    db_session: SessionDep,
    websocket: WebSocket,
    game_session_id: str,
    player_id: int,
    debug: bool = False,
    access_token: str = "",
) -> None:
    try:
        parsed_game_id = UUID(game_session_id)
    except ValueError:
        print(f"[WS] Error: {game_session_id} is not a valid UUID")
        await websocket.close(reason="Invalid game session ID format")
        return

    game_info = db_session.get(GameSessionInfo, parsed_game_id)

    if not game_info or player_id not in game_info.players_ids:
        print("[WS] Error: Invalid game session or player ID")
        await websocket.close(reason="Invalid game session or player ID")
        return

    if not game_info or player_id not in game_info.players_ids:
        print("[WS] Error: Invalid game session or player ID")
        await websocket.close(reason="Invalid game session or player ID")
        return

    if game_info.status == GameSessionStatus.FINISHED:
        await websocket.accept()
        print(
            f"[Game {game_info.session_id}] Cannot start game session which has state FINISHED."
        )
        error_msg = ServerMetaMessage(
            detail="This game session is already finished. Create a new one."
        )
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close(code=1011)
        await manager.disconnect(game_session_id, player_id)
        return

    # Validate tokens and initialize session
    if game_info.registered:
        try:
            user = get_current_user()(access_token, db_session)
            if str(user.id) != str(player_id):
                raise Exception("Invalid token")

        except Exception as e:
            await websocket.accept()
            print(
                f"[Game {game_info.session_id}] Message from {player_id} with invalid 'access_token'."
            )
            error_msg = ServerMetaMessage(
                detail="Invalid access_token. Refusing connection."
            )
            await websocket.send_text(error_msg.model_dump_json())
            await websocket.close(code=1011)
            await manager.disconnect(game_session_id, player_id)
            return

    try:
        await manager.initialize_game_state(
            game_session_id, db_session, game_info, debug
        )
    except NoTracksError as e:
        error_msg = ServerMetaMessage(detail=str(e))
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close(code=1011, reason=str(e))
        await manager.disconnect(game_session_id, player_id)
        return

    await manager.connect(websocket, game_session_id, player_id)

    try:
        expected_number_of_players = len(game_info.players_ids)
        connected_number_of_players = len(
            manager.games[game_session_id].active_connections
        )
        info_msg = ServerMetaMessage(
            msg_type="info",
            detail=f"{connected_number_of_players}/{expected_number_of_players} players connected",
        )
        await manager.broadcast_meta_message(game_id=game_session_id, meta_msg=info_msg)

        if len(manager.games[game_session_id].active_connections) == len(
            game_info.players_ids
        ):
            print("All players connected. Game will proceed.")
            info_msg = ServerMetaMessage(
                msg_type="info", detail="All players connected. Game will proceed now."
            )

            game = manager.games[game_session_id]
            await manager.broadcast_meta_message(game_session_id, info_msg)
            if game.started == False:
                await manager.start_the_game(game_session_id)
            if game.session_disconnect_timer.is_alive():
                seconds_left_on_round = int(
                    (
                        game.expected_round_end_time - game.session_disconnect_time
                    ).total_seconds()
                )
                msg = f"[{game_session_id}] Player with id {player_id} reconnected to session, round will last for another {seconds_left_on_round} seconds."
                logger.info(msg)
                info_msg = ServerMetaMessage(
                    msg_type="info",
                    detail=msg,
                )
                await manager.broadcast_meta_message(
                    game_id=game_session_id, meta_msg=info_msg
                )
                game.session_disconnect_timer.cancel()
                game.round_timer = Timer(
                    seconds_left_on_round,
                    lambda: run(manager.handle_exceeded_round_time(game_session_id)),
                )
                game.round_timer.start()

        while (
            game_session_id in manager.games
            and manager.games[game_session_id].finished == False
        ):
            raw_data = await websocket.receive_json()

            if manager.games[game_session_id].finished == False:
                if not manager.games[game_session_id].started:
                    print("Waiting for other players to join")
                    info_msg = ServerMetaMessage(
                        msg_type="info",
                        detail="Please wait for other players to join",
                    )
                    await websocket.send_text(info_msg.model_dump_json())
                else:
                    try:
                        player_message = PlayerMessage(**raw_data)
                        await manager.process_player_action(
                            game_id=game_session_id,
                            player_id=player_id,
                            data=player_message.model_dump(),
                            players_in_session=game_info.players_ids,
                        )

                    except Exception as e:
                        print(str(e))
                        bad_data_error = f"[WebSocket Validation Error] Bad data from {player_id}: {str(e)}"
                        print(
                            f"[WebSocket Validation Error] Bad data from {player_id}: {str(e)}"
                        )
                        error_msg = ServerMetaMessage(
                            msg_type="error", detail=bad_data_error
                        )
                        await websocket.send_text(error_msg.model_dump_json())
                        continue

    except WebSocketDisconnect:
        await manager.disconnect(game_session_id, player_id)
