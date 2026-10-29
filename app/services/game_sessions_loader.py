from app.config import settings
from app.database import SessionDep
from app.models.game_session import GameSessionInfo, GameSessionInfoPublic, GameSessionStatus
from app.utils.logger import logger
from datetime import datetime, timezone
from sqlmodel import select


class GameSessionsLoader:
    def __init__(self):
        # Maps player id/uuid to a loaded session
        self.player_to_loaded_game_session_map: dict[int, GameSessionInfo] = {}

    async def load_game_session(self, game_session: GameSessionInfo):
        # In near future, will redo it to take in ID only and will load session from DB instead.
        # The way it is now, is for compatibility with other code
        logger.info(f"[GameSessionsLoader] Loading game session {game_session.session_id}")

        for player_id in game_session.players_ids:
            self.player_to_loaded_game_session_map[player_id] = game_session

    async def unload_finished_game_sessions(self, db_session: SessionDep):
        logger.info(
            "[GameSessionsLoader] Checking for game sessions that need to be unloaded"
        )

        # Removing from the in-memory list of registered games
        for k, v in self.player_to_loaded_game_session_map.copy().items():
            # Refreshing state from DB:
            v_from_db = db_session.get(GameSessionInfo, v.session_id)
            if v_from_db == None:
                raise Exception(
                    f"[GameSessionsLoader][{v.session_id}] Game session is no longer in DB"
                )

            v = v_from_db

            if v.status == GameSessionStatus.FINISHED:
                logger.info(
                    f"[GameSessionsLoader] Unloading game session {v.session_id} for player with id {k}"
                )
                del self.player_to_loaded_game_session_map[k]

    async def unload_and_delete_stale_game_sessions(self, db_session: SessionDep):
        logger.info("[GameSessionLoader] Unloading and removing stale game sessions")
        loaded_waiting_game_sessions = {
            player_id: game_session
            for player_id, game_session in self.player_to_loaded_game_session_map.items()
            if game_session.status == GameSessionStatus.WAITING_FOR_PLAYERS
        }

        # Unloading
        for player_id, game_session in loaded_waiting_game_sessions.items():
            assert isinstance(game_session.created_at, datetime)
            time_passed = datetime.now(tz=timezone.utc) - game_session.created_at.replace(tzinfo=timezone.utc)

            if (
                int(time_passed.total_seconds() / 60)
                >= settings.REGISTERED_SESSION_START_TIMEOUT
            ):
                logger.info(
                    f"[GameSessionLoader] {player_id} : {game_session.session_id} has been unloaded after waiting for {time_passed}"
                )

                if (
                    self.player_to_loaded_game_session_map[player_id].status
                    == GameSessionStatus.WAITING_FOR_PLAYERS
                ):  # Shouldn't happen. Sanity check
                    del self.player_to_loaded_game_session_map[player_id]

        # Deleting from DB
        db_waiting_game_sessions = (
            db_session.exec(
                select(GameSessionInfo).where(
                    GameSessionInfo.status == GameSessionStatus.WAITING_FOR_PLAYERS
                )
            )
        ).all()

        for game_session in db_waiting_game_sessions:
            assert isinstance(game_session.created_at, datetime)
            time_passed = datetime.now(tz=timezone.utc) - game_session.created_at.replace(tzinfo=timezone.utc)
            logger.info(
                f"[{game_session.session_id}] has been waiting for {time_passed}"
            )

            if (
                int(time_passed.total_seconds() / 60)
                >= settings.REGISTERED_SESSION_START_TIMEOUT
            ):
                logger.info(
                    f"[{game_session.session_id}] has been deleted from database after waiting for {time_passed}"
                )
                db_session.delete(game_session)

        db_session.commit()

game_sessions_loader = GameSessionsLoader()
