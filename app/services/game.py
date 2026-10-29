from app.models.game_session import GameSessionInfo, GameSessionInfoPublic, GameSessionStatus
from app.models.message import ServerMessage, ServerMetaMessage
from app.models.track import Track, TrackPublic
from app.services.game_sessions_loader import game_sessions_loader
from app.utils.crud import read_user_by_id
from app.utils.logger import logger

import asyncio
import random
import threading
import uuid

from datetime import datetime, timedelta, timezone
from fastapi import WebSocket
from sqlmodel import select, Session
from typing import Any

from app.database import engine, SessionDep
from app.config import settings


class NoTracksError(Exception):
    """Raised when the database has no tracks to start a game."""


class ActiveGameSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.active_connections: dict[int, WebSocket] = {}
        self.playlist: list[TrackPublic] = []
        self.matched_tracks: dict[int, list[TrackPublic]] = {}
        self.revealed_tracks: list[TrackPublic] = []
        self.player_gave_answer: dict[int, bool] = {}
        self.registered: bool = (
            False  # Registered means that it's for registered users. i.e. tokens needed
        )
        self.current_guess_track: TrackPublic | None = None
        self.current_song_audio_url: str | None = None
        self.started: bool = False
        self.finished: bool = False
        self.current_round_number: int = 0
        self.round_start_time: datetime
        self.expected_round_end_time: datetime
        self.game_session_metadata: GameSessionInfoPublic
        self.session_disconnect_timer: threading.Timer
        self.session_disconnect_time: datetime
        self.round_timer: threading.Timer


class GameConnectionManager:
    def __init__(self) -> None:
        self.games: dict[str, ActiveGameSession] = {}

    async def connect(self, websocket: WebSocket, game_id: str, player_id: int) -> None:
        await websocket.accept()
        game = self.games[game_id]
        game.active_connections[player_id] = websocket

    async def disconnect(self, game_id: str, player_id: int) -> None:
        game = self.games.get(game_id)
        if game:
            if player_id in game.active_connections:
                try:
                    await game.active_connections[player_id].close()
                except Exception:
                    pass
                finally:
                    try:
                        del game.active_connections[player_id]
                    except Exception:
                        pass

                    if game.started == True and game.finished == False:
                        msg = (
                            f"[{game_id}]"
                            f"Session will wait {settings.SESSION_DISCONNECT_TERMINATION_TIME} seconds"
                            f"for player with id {player_id} to reconnect, else the session will end."
                        )
                        logger.info(msg)

                        if game.round_timer.is_alive():
                            game.round_timer.cancel()

                        game.session_disconnect_timer = threading.Timer(
                            settings.SESSION_DISCONNECT_TERMINATION_TIME,
                            lambda: asyncio.run(
                                self.finish_game(game_id=game_id, reason="Player with id {player_id} left the game.")
                            ),
                        )
                        game.session_disconnect_timer.start()
                        game.session_disconnect_time = datetime.now(timezone.utc)

                        info_msg = ServerMetaMessage(
                            msg_type="info",
                            detail=msg,
                        )
                        await manager.broadcast_meta_message(
                            game_id=game_id, meta_msg=info_msg
                        )

            if not game.active_connections:
                del self.games[game_id]

    async def initialize_game_state(
        self,
        game_id: str,
        db_session: SessionDep,
        game_info: GameSessionInfo,
        debug: bool,
    ) -> None:
        if game_id not in self.games:
            self.games[game_id] = ActiveGameSession(session_id=game_id)

        game = self.games[game_id]

        if game.started == False:
            game.registered = game_info.registered
            players_ids = game_info.players_ids
            game.game_session_metadata = GameSessionInfoPublic.model_validate(
                game_info.model_dump()
            )
            game.session_disconnect_timer = threading.Timer(
                settings.SESSION_DISCONNECT_TERMINATION_TIME,
                lambda: asyncio.run(
                    self.finish_game(game_id=game_id, reason="Player left.")
                ),
            )
            game.round_timer = threading.Timer(
                game.game_session_metadata.seconds_per_round,
                lambda: asyncio.run(self.handle_exceeded_round_time(game_id)),
            )

            if not game.playlist:
                db_tracks = db_session.exec(select(Track)).all()

                if not db_tracks:
                    raise NoTracksError(
                        "No tracks in the database — add some tracks first."
                    )
                game.playlist = [TrackPublic.model_validate(t) for t in db_tracks]

                if not debug:
                    random.shuffle(game.playlist)

            for p_id in players_ids:
                if not game.matched_tracks.get(p_id):
                    game.matched_tracks[p_id] = []

                if p_id not in game.player_gave_answer:
                    game.player_gave_answer[p_id] = False

    async def process_player_action(
        self,
        game_id: str,
        player_id: int,
        data: dict[str, Any],
        players_in_session: list[int],
    ) -> None:
        game = self.games[game_id]

        if "answer" not in data:
            logger.info(
                f"[{game_id}] Message from {player_id} without 'answer' field - ignoring."
            )
            return

        logger.info(
            f"[{game_id}] Received answer from {player_id}: {data['answer']}."
        )

        submitted: int = data["answer"]
        game.player_gave_answer[player_id] = True
        board: list[TrackPublic] = game.matched_tracks[player_id]

        assert game.current_guess_track is not None
        guess_year = game.current_guess_track.year

        year_by_id: list[int] = [t.year for t in board]
        correct = all(year <= guess_year for year in year_by_id[:submitted]) and all(
            year >= guess_year for year in year_by_id[submitted:]
        )

        if correct:
            logger.info(f"[{game_id}] Correct answer from {player_id}: {submitted}.")

            if not game.current_guess_track in game.matched_tracks[player_id]:
                game.matched_tracks[player_id].insert(
                    submitted, game.current_guess_track
                )

            if not game.current_guess_track in game.revealed_tracks:
                game.revealed_tracks.append(game.current_guess_track)

        if all(
            game.player_gave_answer.get(p_id) for p_id in players_in_session
        ) and not (await self.is_game_finished(game_id)):
            await self.start_new_round(game_id)

    async def broadcast_game_state(
        self, game_id: str, player_ids: list[int]
    ) -> None:
        game = self.games[game_id]

        matched_tracks_uuids = {
            player_id: [
                {"track_id": track.track_id} for track in game.matched_tracks[player_id]
            ]
            for player_id in player_ids
        }

        for player_id in player_ids:
            server_message = ServerMessage(
                player_id=player_id,
                matched_tracks=matched_tracks_uuids,
                current_song_audio_url=game.current_song_audio_url or "",
                started=game.started,
                finished=game.finished,
                tracks_data=game.revealed_tracks,
                current_round_number=game.current_round_number,
                game_session_metadata=game.game_session_metadata,
            )

            if player_id in game.active_connections:
                connection = game.active_connections[player_id]
                try:
                    await connection.send_text(server_message.model_dump_json())
                except Exception as e:
                    logger.error(f"[{game_id}] Error sending via WebSocket: {str(e)}.")

    async def broadcast_meta_message(
        self, game_id: str, meta_msg: ServerMetaMessage
    ) -> None:
        game = self.games[game_id]

        for _, connection in game.active_connections.items():
            try:
                await connection.send_text(meta_msg.model_dump_json())
            except Exception as e:
                logger.error(f"[{game_id}] Error sending Meta Message via WebSocket: {str(e)}.")

    async def start_the_game(self, game_id: str):
        game = self.games[game_id]

        with Session(engine) as db_session:
            game_session_from_db = db_session.get(
                GameSessionInfo, uuid.UUID(game_id)
            )

            if game_session_from_db == None:
                raise Exception(f"[{game_id}] Game session is no longer in DB.")
            else:
                if game_session_from_db.status != GameSessionStatus.IN_PROGRESS:
                    game_session_from_db.status = GameSessionStatus.IN_PROGRESS
                    db_session.add(game_session_from_db)
                    db_session.commit()
                    db_session.refresh(game_session_from_db)
                    game.game_session_metadata = GameSessionInfoPublic.model_validate(
                        game_session_from_db.model_dump()
                    )

            game.started = True

        game.current_round_number = 0
        game.current_guess_track = game.playlist.pop()
        game.current_song_audio_url = game.current_guess_track.preview_url
        game.revealed_tracks.append(game.current_guess_track)

        for player_id in game.game_session_metadata.players_ids:
            game.matched_tracks[player_id].insert(0, game.current_guess_track)

        await self.start_new_round(game_id)

    async def start_new_round(self, game_id: str) -> None:
        game = self.games[game_id]
        logger.info(f"[{game_id}] Starting round number {game.current_round_number + 1}.")

        if game.session_disconnect_timer.is_alive():
            game.session_disconnect_timer.join()

        game.round_timer.cancel()
        game.current_round_number += 1
        game.current_guess_track = game.playlist.pop()
        game.current_song_audio_url = game.current_guess_track.preview_url

        for k in game.player_gave_answer:
            game.player_gave_answer[k] = False

        if game.finished == False:
            game.round_timer = threading.Timer(
                game.game_session_metadata.seconds_per_round,
                lambda: asyncio.run(self.handle_exceeded_round_time(game_id)),
            )
            game.round_timer.start()
            game.round_start_time = datetime.now(timezone.utc)
            game.expected_round_end_time = game.round_start_time + timedelta(
                seconds=game.game_session_metadata.seconds_per_round
            )

        await manager.broadcast_game_state(
            game_id, game.game_session_metadata.players_ids
        )

    async def handle_exceeded_round_time(self, game_id: str) -> None:
        msg = f"[{game_id}] Round time exceeded. Starting next round."
        logger.info(msg)

        info_msg = ServerMetaMessage(
            msg_type="info", detail=msg
        )
        await manager.broadcast_meta_message(game_id=game_id, meta_msg=info_msg)

        if not (await self.is_game_finished(game_id)):
            await self.start_new_round(game_id)

    async def is_game_finished(self, game_id: str):
        game = self.games[game_id]

        if game.finished == True:
            return True
        else:
            if game.current_round_number >= game.game_session_metadata.rounds:
                await self.finish_game(
                    game_id=game_id,
                    reason="Rounds limit reached.",
                )
                return True
            elif not game.playlist:
                await self.finish_game(
                    game_id=game_id,
                    reason="Not enough songs in playlist.",
                )
                return True

        return False

    async def finish_game(self, game_id: str, reason: str) -> None:
        logger.info(f"[{game_id}] Game is finished | Reason: {reason}")

        game = self.games[game_id]
        game.finished = True

        if game.round_timer.is_alive():
            game.round_timer.cancel()

        if game.session_disconnect_timer.is_alive():
            game.session_disconnect_timer.cancel()

        with Session(engine) as db_session:
            ids_of_players_assigned_to_session = game.game_session_metadata.players_ids

            # Adding score for players:
            if game.game_session_metadata.registered == True:
                for player_id in ids_of_players_assigned_to_session:
                    score = len(game.matched_tracks[player_id])
                    user = read_user_by_id(db_session, int(player_id))
                    assert user != None
                    user.score += score
                    db_session.add(user)
                    db_session.commit()
                    db_session.refresh(user)

            # Updating the DB session info
            game_session = db_session.exec(
                select(GameSessionInfo).where(
                    GameSessionInfo.session_id == uuid.UUID(game_id)
                )
            )
            game_session = game_session.one()
            game_session.status = GameSessionStatus.FINISHED
            db_session.add(game_session)

            db_session.commit()
            db_session.refresh(game_session)

        await manager.broadcast_game_state(
            game_id, game.game_session_metadata.players_ids
        )

        info_msg = ServerMetaMessage(msg_type="info", detail="Game is finished")
        await manager.broadcast_meta_message(game_id=game_id, meta_msg=info_msg)

        for player_id in game.game_session_metadata.players_ids:
            await manager.disconnect(game_id, player_id)

        await game_sessions_loader.unload_finished_game_sessions(db_session)



manager = GameConnectionManager()
