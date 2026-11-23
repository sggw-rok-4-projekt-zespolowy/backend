from asyncio import sleep
from app.models.game_session import (
    GameSessionInfo,
    GameSessionInfoPublic,
    GameSessionState,
    InitializedGameSession,
)
from app.models.message import PlayerMessage, ServerMessage, ServerMetaMessage
from app.models.player import Player, PlayerState
from app.models.round import Round, RoundState
from app.models.track import Track, TrackPublic
from app.services.game_sessions_loader import game_sessions_loader
from app.utils.crud import (
    read_user_by_id,
    read_game_session_info_by_game_session_id,
    update_game_session_info,
    update_user
)
from app.utils.dependencies import get_current_user
from app.utils.logger import logger
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError, loads
from random import choice
from sqlmodel import col
from threading import Timer
from uuid import UUID

import asyncio
import random

from fastapi import Depends, WebSocket
from starlette.websockets import WebSocketState
from sqlmodel import select, Session
from typing import Any

from app.database import engine, get_session
from app.config import settings


class GameConnectionManager:
    def __init__(self) -> None:
        self.games: dict[str, InitializedGameSession] = {}

    # Game loop methods ------------------------------------------------------- #

    async def addTrackToTracksHistory(self, game_session_id: str):
        game = self.games[game_session_id]
        track = game.current_round.track
        assert track != None
        game.previous_tracks.append(track)
        game.previous_tracks.sort(key=lambda x: x.year)

    async def acknowledgeGameState(self, websocket: WebSocket, game_session_id: str):
        # Acknowledge current game state:
        game = self.games[game_session_id]
        msg = f"Game session state is: {game.game_session_info.state}"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def broadcastGameDetails(self, game_session_id: str):
        game = self.games[game_session_id]
        for player_id, player in game.connected_players.items():
            await self.sendGameDetails(player.websocket, game_session_id, player_id)

    async def broadcastInfoMessage(self, game_session_id: str, msg: str):
        game = self.games[game_session_id]
        for player_id, player in game.connected_players.items():
            await self.sendInfoMessage(
                player.websocket, game_session_id, msg, player_id
            )

    async def checkAnswers(self, game_session_id: str):
        game = self.games[game_session_id]
        all_players = {**game.connected_players, **game.disconnected_players}

        for player in all_players.values():
            assert game.current_round.track != None
            correct_year = game.current_round.track.year

            if player.answer != None:
                # Not too clear, but we're checking if the index given by player is correct
                # For when sorting by year. TODO: Definitely untangle.
                tracks_years: list[int] = [t.year for t in player.matched_tracks]
                correct = all(
                    year <= correct_year for year in tracks_years[: player.answer]
                ) and all(
                    year >= correct_year for year in tracks_years[player.answer :]
                )
            else:
                correct = False

            if correct:
                player.matched_tracks.append(game.current_round.track)
                player.matched_tracks.sort(key=lambda x: x.year)
                player.correct_answers += 1

    async def chooseNextTrack(self, db_session: Session, game_session_id: str):
        previous_tracks = self.games[game_session_id].previous_tracks

        tracks = db_session.exec(
            select(Track).where(
                col(Track.track_id).notin_(
                    [track.track_id for track in previous_tracks]
                )
            )
        ).all()

        return TrackPublic.model_validate(choice(tracks))

    async def decideGameState(self, game_session_id):
        game = self.games[game_session_id]

        prev_game_state = game.game_session_info.state

        if game.game_session_info.state == GameSessionState.WAITING_FOR_PLAYERS:
            if await self.allPlayersConnected(game_session_id):
                game.game_session_info.state = GameSessionState.IN_PROGRESS

        elif game.game_session_info.state == GameSessionState.IN_PROGRESS:
            if (
                game.current_round.state == RoundState.FINISHED
                and game.current_round.number == game.game_session_info.rounds
            ):
                game.game_session_info.state = GameSessionState.FINISHED

        if (
            game.game_session_info.state != GameSessionState.FINISHED
            and len(game.disconnected_players) > 0
        ):
            game.game_session_info.state = GameSessionState.PLAYER_DISCONNECTION

        if (
            game.game_session_info.state == GameSessionState.PLAYER_DISCONNECTION
            and len(game.disconnected_players) == 0
        ):
            game.game_session_info.state = GameSessionState.IN_PROGRESS

        if (
            game.game_session_info.state == GameSessionState.PLAYER_DISCONNECTION
            and game.disconnect_timeout_end_time
            and game.disconnect_timeout_end_time < datetime.now(timezone.utc)
        ):
            game.game_session_info.state = GameSessionState.TIMED_OUT

        # Broadcast message about game session state if it changed
        if game.game_session_info.state != prev_game_state:
            await self.broadcastInfoMessage(
                game_session_id,
                f"Game session state is: {game.game_session_info.state}",
            )

    def disconnectionCountStarted(self, game_session_id):
        game = self.games[game_session_id]
        if game.disconnect_timeout_end_time != None:
            return True
        else:
            return False

    async def setPlayersState(self, game_session_id, state: PlayerState):
        game = self.games[game_session_id]
        all_players = {**game.connected_players, **game.disconnected_players}

        for player_id in all_players.keys():
            self.setPlayerState(game_session_id, player_id, state)

    async def updateGameSessionInDatabase(
        self, db_session: Session, game_session_id: str
    ):
        game = self.games[game_session_id]

        game_session_info_from_db = read_game_session_info_by_game_session_id(
            db_session, game_session_id
        )
        assert game_session_info_from_db != None

        # Updates
        game_session_info_from_db.state = game.game_session_info.state

        update_game_session_info(db_session, game_session_info_from_db)
        await self.broadcastInfoMessage(
            game_session_id, f"Game session state saved to database"
        )

    async def updatePlayersInDatabase(
        self, db_session: Session, game_session_id: str
    ):
        game = self.games[game_session_id]

        for player_id, player in game.connected_players.items():
            user = read_user_by_id(db_session, player_id)

            assert user != None

            user.score += player.correct_answers

            update_user(db_session, user)

            await self.sendInfoMessage(
                player.websocket, game_session_id, f"Player score saved to database", player_id
            )

    async def finishRound(self, db_session: Session, game_session_id: str):
        game = self.games[game_session_id]

        # Change state and inform about finishing the round
        game.current_round.state = RoundState.FINISHED
        await self.broadcastInfoMessage(
            game_session_id, f"Round number {game.current_round.number} finished"
        )

    async def shouldContinueGameLoop(self, game_session_id):
        return (
            await manager.allPlayersConnected(game_session_id)
            and self.games[game_session_id].game_session_info.state
            != GameSessionState.FINISHED
        )

    async def shouldGameEnd(self, game_session_id):
        should_game_end = False
        game = self.games[game_session_id]

        if self.getGameState(game_session_id) == GameSessionState.FINISHED:
            should_game_end = True

        if self.getGameState(game_session_id) == GameSessionState.TIMED_OUT:
            should_game_end = True

        return should_game_end

    async def shouldRoundFinish(self, game_session_id):
        should_round_finish = True

        game = self.games[game_session_id]
        all_players = {**game.connected_players, **game.disconnected_players}

        if game.current_round.state != RoundState.IN_PROGRESS:
            should_round_finish = False

        for player in all_players.values():
            if player.state == PlayerState.ANSWERING:
                should_round_finish = False

        # No matter what, if round time exceeded, finish the round.
        assert game.current_round.end_time != None
        current_time = datetime.now(timezone.utc)
        if current_time > game.current_round.end_time:
            should_round_finish = True

        return should_round_finish

    async def shouldRoundStart(self, game_session_id):
        game = self.games[game_session_id]
        if (
            game.game_session_info.state == GameSessionState.IN_PROGRESS
            and game.current_round.state != RoundState.IN_PROGRESS
        ):
            return True
        else:
            return False

    async def startDisconnectionCount(self, game_session_id):
        game = self.games[game_session_id]
        game.disconnect_timeout_end_time = datetime.now(timezone.utc) + timedelta(
            seconds=settings.SESSION_DISCONNECT_TERMINATION_TIME
        )
        await self.broadcastInfoMessage(
            game_session_id,
            f"Player disconnection. Game will end at {game.disconnect_timeout_end_time} (UTC) if the player doesn't reconnect",
        )

    async def stopDisconnectionCount(self, game_session_id):
        game = self.games[game_session_id]
        game.disconnect_timeout_end_time = None
        await self.broadcastInfoMessage(
            game_session_id, f"All players reconnected. Game will continue"
        )

    async def runGameLoop(self, game_session_id: str):
        game = self.games[game_session_id]
        current_round = game.current_round

        game.game_loop_running = True
        self.logInfoMessage(game_session_id, "Game loop is starting")

        with Session(engine) as db_session:
            while self.isGameLoopRunning(game_session_id):
                await self.decideGameState(game_session_id)

                if self.getGameState(game_session_id) == GameSessionState.IN_PROGRESS:
                    if await self.shouldRoundStart(game_session_id):
                        await self.startRound(db_session, game_session_id)
                        await self.broadcastGameDetails(game_session_id)

                    if await self.shouldRoundFinish(game_session_id):
                        await self.finishRound(db_session, game_session_id)
                        await self.addTrackToTracksHistory(game_session_id)
                        await self.checkAnswers(game_session_id)
                        await self.setPlayersState(
                            game_session_id, PlayerState.ANSWERING
                        )

                if (
                    self.getGameState(game_session_id)
                    == GameSessionState.PLAYER_DISCONNECTION
                ):
                    if not self.disconnectionCountStarted(game_session_id):
                        await self.startDisconnectionCount(game_session_id)
                else:
                    if self.disconnectionCountStarted(game_session_id):
                        await self.stopDisconnectionCount(game_session_id)

                if await self.shouldGameEnd(game_session_id):
                    game.game_loop_running = False
                    await self.updateGameSessionInDatabase(
                        db_session, game_session_id
                    )
                    await self.updatePlayersInDatabase(
                        db_session, game_session_id
                    )

                    # TODO: Update players score in DB after the game
                    await self.broadcastGameDetails(game_session_id)

                await sleep(settings.GAME_LOOP_TICK_TIME)

    async def sendGameDetails(
        self, websocket: WebSocket, game_session_id: str, player_id: str
    ):
        game = self.games[game_session_id]
        players = game.connected_players

        self.logInfoMessage(
            game_session_id,
            f"Sending game details to the player",
            player_id,
        )

        assert game.current_round.track != None

        # TODO: Sending old payload for compatibility. Not everthing might be needed.
        matched_tracks = {player_id: player.matched_tracks for player_id, player in players.items()}

        server_message = ServerMessage(
            player_id=player_id,
            matched_tracks=matched_tracks,
            current_song_audio_url=game.current_round.track.preview_url,
            started=game.game_session_info.state == GameSessionState.IN_PROGRESS,
            finished=game.game_session_info.state == GameSessionState.FINISHED
            or game.game_session_info.state == GameSessionState.TIMED_OUT,
            tracks_data=game.previous_tracks,
            current_round_number=game.current_round.number,
            game_session_metadata=GameSessionInfoPublic.model_validate(
                game.game_session_info
            ),
        )

        msg = server_message.model_dump_json(indent=2)
        await self.sendInfoMessage(websocket, game_session_id, msg)

    def isGameLoopRunning(self, game_session_id):
        return self.games[game_session_id].game_loop_running
        # return (
        #     await manager.allPlayersConnected(game_session_id) and
        #     not manager.getRoundState(game_session_id) == RoundState.IN_PROGRESS and
        #     not self.games[game_session_id].game_session_info.state == GameSessionState.FINISHED
        # )

    async def startRound(self, db_session: Session, game_session_id: str):
        game = self.games[game_session_id]
        seconds_per_round = self.games[
            game_session_id
        ].game_session_info.seconds_per_round

        # Increment round number
        if game.current_round.state != RoundState.INITIAL_ROUND:
            game.current_round.number += 1

        # Choose track for this round
        game.current_round.track = await self.chooseNextTrack(
            db_session, game_session_id
        )

        # Set end time
        game.current_round.end_time = datetime.now(timezone.utc) + timedelta(
            seconds=seconds_per_round
        )

        # Change state and inform about starting the round
        game.current_round.state = RoundState.IN_PROGRESS
        await self.broadcastInfoMessage(
            game_session_id, f"Round number {game.current_round.number} starting"
        )

    # END: Game loop methods --------------------------------------------------- #

    # Player communication and state methods ----------------------------------- #

    async def acknowledgeConnectionRequest(
        self, websocket: WebSocket, game_session_id: str
    ):
        msg = "Received WS connection request"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def allPlayersConnected(self, game_session_id):
        game = self.games[game_session_id]
        if len(game.connected_players) < len(game.game_session_info.players_ids):
            return False
        else:
            return True

    async def acknowledgeGameSessionInitialized(
        self, websocket: WebSocket, game_session_id: str
    ):
        # Acknowledge game initialized:
        msg = "Game session is initialized"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def acknowledgePlayerMessage(
        self, websocket: WebSocket, game_session_id: str, player_message: str
    ):
        # Acknowledge received player message:
        msg = f"Server received message: {player_message}"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def acknowledgePlayerState(
        self, websocket: WebSocket, game_session_id: str, player_id: str
    ):
        # Acknowledge player state:
        player = self.games[game_session_id].connected_players[player_id]
        msg = f"Player state is: {player.state}"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def acknowledgeValidPlayerGuess(
        self, websocket: WebSocket, game_session_id: str
    ):
        msg = f"Player's guess message is valid"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def acknowledgeValidConnectionRequest(
        self, websocket: WebSocket, game_session_id: str, player_id: str
    ):
        msg = f"Received WS connection request is valid"
        await self.sendInfoMessage(websocket, game_session_id, msg, player_id)

    async def answerAlreadyGivenMessage(
        self, websocket: WebSocket, game_session_id: str
    ):
        msg = "Player answer was already received"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def connectPlayer(
        self, websocket: WebSocket, game_session_id: str, player_id: str
    ):
        if self.isPlayerReconnecting(game_session_id, player_id):
            # Handle reconnection
            self.games[game_session_id].connected_players[player_id] = self.games[
                game_session_id
            ].disconnected_players[player_id]

            # Assign new WebSocket
            self.games[game_session_id].connected_players[
                player_id
            ].websocket = websocket
            del self.games[game_session_id].disconnected_players[player_id]

            # Resend game details if player disconnected, when the game already started
            if self.getGameState(game_session_id) == GameSessionState.PLAYER_DISCONNECTION:
                await self.sendGameDetails(websocket, game_session_id, player_id)

            msg = f"Reconnected player with id: {player_id}"
        else:
            # Handle first connection
            # Arguments passed to Player() ensure first round is skipped, so that a card is placed on the table.
            self.games[game_session_id].connected_players[player_id] = Player(
                websocket=websocket
            )
            msg = f"Connected player with id: {player_id}"

        await self.sendInfoMessage(websocket, game_session_id, msg)

    def decidePlayerState(self, game_session_id, player_id):
        game = self.games[game_session_id]
        player = self.games[game_session_id].connected_players[player_id]
        if game.current_round.number == player.number_of_guesses:
            player.state = PlayerState.ANSWERED
        else:
            player.state = PlayerState.ANSWERING

    async def roundNotInProgressMessage(
        self, websocket: WebSocket, game_session_id: str
    ):
        msg = f"Round must be in progress for answer to be considered. Player message is discarded"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    async def disconnectPlayer(
        self, websocket: WebSocket, game_session_id: str, player_id: str
    ):
        self.games[game_session_id].disconnected_players[player_id] = self.games[
            game_session_id
        ].connected_players[player_id]
        del self.games[game_session_id].connected_players[player_id]
        msg = f"Player with id: {player_id} disconnected"
        await self.sendInfoMessage(websocket, game_session_id, msg)

    def getGameState(self, game_session_id: str):
        return self.games[game_session_id].game_session_info.state

    def getPlayerState(self, game_session_id: str, player_id: str):
        return self.games[game_session_id].connected_players[player_id].state

    def getRoundState(self, game_session_id: str):
        return self.games[game_session_id].current_round.state

    def initializeGameSession(self, db_session: Session, game_session_id: str):
        game_session_info = read_game_session_info_by_game_session_id(
            db_session, game_session_id
        )

        if not game_session_info:
            raise ValueError("Couldn't get the game session info")

        self.games[game_session_id] = InitializedGameSession(
            game_session_info=game_session_info
        )

    def keepPlayersConnected(self, game_session_id: str):
        return (
            self.games[game_session_id].game_session_info.state
            != GameSessionState.FINISHED
        )

    def isGameSessionInitialized(self, game_session_id: str):
        return game_session_id in self.games

    def isPlayerConnected(self, game_session_id, player_id):
        return player_id in self.games[game_session_id].connected_players

    def isPlayerReconnecting(self, game_session_id: str, player_id: str):
        return player_id in self.games[game_session_id].disconnected_players

    def logInfoMessage(
        self, game_session_id: str, msg: str, player_id: str | None = None
    ):
        if player_id:
            logger.info(
                f"[WS] - GameSession id: {game_session_id} - Player id: {player_id} - {msg}"
            )
        else:
            logger.info(f"[WS] - GameSession id: {game_session_id} - {msg}")

    def processPlayerGuess(
        self, game_session_id: str, player_id: str, player_message: str
    ):
        game = self.games[game_session_id]
        player = self.games[game_session_id].connected_players[player_id]

        player_message_parsed = PlayerMessage.model_validate_json(player_message)
        player.number_of_guesses += 1
        player.answer = player_message_parsed.answer

    async def sendErrorMessage(
        self, websocket: WebSocket, game_session_id: str, msg: str
    ):
        await websocket.send_text(msg)
        logger.error(f"[WS] - {game_session_id} - {msg}")

    async def sendInfoMessage(
        self,
        websocket: WebSocket,
        game_session_id: str,
        msg: str,
        player_id: str | None = None,
    ):
        await websocket.send_text(msg)
        self.logInfoMessage(game_session_id, msg, player_id)

    def setPlayerState(self, game_session_id, player_id, state: PlayerState):
        game = self.games[game_session_id]
        all_players = {**game.connected_players, **game.disconnected_players}

        all_players[player_id].state = state

    async def validateConnectionRequest(
        self,
        websocket: WebSocket,
        db_session: Session,
        game_session_id: str,
        player_id: str,
        access_token: str,
    ) -> str:

        try:
            game_session_info = db_session.get(GameSessionInfo, game_session_id)
            if not game_session_info or player_id not in game_session_info.players_ids:
                raise ValueError("Couldn't find the game session")

            if game_session_info.state == GameSessionState.FINISHED:
                raise ValueError("Cannot start game session which has state FINISHED")

            if game_session_info.state == GameSessionState.TIMED_OUT:
                raise ValueError("Cannot start game session which has state TIMED_OUT")

            if game_session_info.registered:
                user = None

                try:
                    user = get_current_user()(access_token, db_session)
                except Exception as e:
                    raise ValueError(
                        f"'access_token' incorrect or missing for player with id: {player_id}"
                    )

                if user and str(user.id) != str(player_id):
                    raise ValueError(
                        f"'access_token' incorrect or missing for player with id: {player_id}"
                    )

            db_tracks = db_session.exec(select(Track)).all()
            if not db_tracks:
                raise ValueError(f"No tracks in the database. Add some tracks first")

        except ValueError as e:
            return str(e)

        return ""

    async def validatePlayerMessage(
        self, websocket: WebSocket, game_session_id: str, player_guess: str
    ):
        try:
            PlayerMessage.model_validate_json(player_guess)

        except Exception as e:
            return str(e)

        return ""


manager = GameConnectionManager()
