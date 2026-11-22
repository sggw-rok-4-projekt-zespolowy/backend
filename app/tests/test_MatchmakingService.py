import pytest
from app.models.game_session import (
    GameSessionInfo,
    GameSessionInfoCreate,
    GameSessionState,
    GameSessionVariant,
    InitializedGameSession,
)
from app.services import matchmaking as matchmaking_module
from app.services.game import manager
from app.services.matchmaking import MatchmakingService
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, StaticPool, SQLModel
from time import sleep

@pytest.fixture(name="engine_monkeypatch")
def engine_monkeypatch(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr("app.services.matchmaking.engine", engine)

@pytest.fixture(name="settings_monkeypatch")
def settings_monkeypatch(monkeypatch):
    monkeypatch.setattr("app.config.settings.STALE_MATCHMAKING_REQUEST_TIME", 5)


def test_createRequest_creates_valid_request(engine_monkeypatch):
    ms = MatchmakingService()

    request = ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate() # GameSessionInfo with defaults
        )

    assert request.requestOwnerId == "1"
    assert request.requestedGameSessionInfo.rounds == 7


def test_findRequestByOwner_finds_existing_request_by_owner(engine_monkeypatch):
    ms = MatchmakingService()

    ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate() # GameSessionInfo with defaults
        )

    request = ms.findRequestByOwner(
            requestOwnerId = "1"
        )

    assert request != None
    assert request.requestOwnerId == "1"
    assert request.requestedGameSessionInfo.rounds == 7


def test_fulfillRequest_fulfills_request_if_conditions_met(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "2",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "3",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "4",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestFulfilled = ms.fulfillRequest(requestsMade[0])

    assert requestFulfilled == True
    assert requestsMade[0].fulfilled == True
    assert requestsMade[1].fulfilled == False
    assert requestsMade[2].fulfilled == True
    assert requestsMade[3].fulfilled == False
    assert requestsMade[0].createdGameSessionInfo == requestsMade[2].createdGameSessionInfo
    assert ["1", "3"] == requestsMade[0].createdGameSessionInfo.players_ids

def test_fulfillRequest_fulfills_request_if_conditions_met_singleplayer(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.SINGLE)
        )
    )

    requestFulfilled = ms.fulfillRequest(requestsMade[0])

    assert requestFulfilled == True
    assert requestsMade[0].fulfilled == True
    assert requestsMade[0].createdGameSessionInfo != None
    assert ["1"] == requestsMade[0].createdGameSessionInfo.players_ids

def test_isRequestStale_deleteRequest_remove_stale_request_when_appropriate(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "2",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestFulfilled = ms.fulfillRequest(requestsMade[1])

    if ms.isRequestStale(
            requestsMade[0],
            timedelta(seconds=5)
        ):
        ms.deleteRequest(requestsMade[0])

    with pytest.raises(ValueError):

        requestsMade.append(
            ms.createRequest(
                requestOwnerId = "1",
                requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
            )
        )

    assert len(ms.requests.values()) == 2

    sleep(7)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "3",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 3, variant=GameSessionVariant.DUEL)
        )
    )

    if ms.isRequestStale(
            requestsMade[0],
            timedelta(seconds=5)
        ):
        ms.deleteRequest(requestsMade[0])

    assert len(ms.requests.values()) == 1

def test_removeStaleRequests_removes_stale_request_when_appropriate(engine_monkeypatch, settings_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "2",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestFulfilled = ms.fulfillRequest(requestsMade[1])

    ms.removeStaleRequests()

    with pytest.raises(ValueError):

        requestsMade.append(
            ms.createRequest(
                requestOwnerId = "1",
                requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
            )
        )

    assert len(ms.requests.values()) == 2

    sleep(7)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "3",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 3, variant=GameSessionVariant.DUEL)
        )
    )

    ms.removeStaleRequests()

    assert len(ms.requests.values()) == 1


def test_removeStaleRequests_doesnt_affect_not_fulfilled_requests(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = "2",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
        )
    )

    assert len(ms.requests.values()) == 2

    ms.removeStaleRequests()

    assert len(ms.requests.values()) == 2




# Regression tests for issue #7:
# Removing a stale MatchmakingRequest must not remove a GameSessionInfo that is
# still needed - neither the session of a game that is still being played, nor
# the session of a game that already finished (match history).

def _createFulfilledDuelRequestWithOldSession(ms: MatchmakingService, minutesOld: int = 5) -> str:
    """Creates a matched DUEL pair and returns the id of the created game session."""
    requestOne = ms.createRequest(
            requestOwnerId = "1",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    ms.createRequest(
            requestOwnerId = "2",
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    ms.fulfillRequest(requestOne)
    assert requestOne.createdGameSessionInfo != None

    sessionId = requestOne.createdGameSessionInfo.session_id

    # Making the session old enough for the stale check to fire.
    with Session(matchmaking_module.engine) as dbSession:
        gameSessionInfo = dbSession.get(GameSessionInfo, sessionId)
        assert gameSessionInfo != None
        gameSessionInfo.created_at = datetime.utcnow() - timedelta(minutes = minutesOld)
        dbSession.add(gameSessionInfo)
        dbSession.commit()

    return sessionId


def _readGameSessionInfo(sessionId: str) -> GameSessionInfo | None:
    with Session(matchmaking_module.engine) as dbSession:
        return dbSession.get(GameSessionInfo, sessionId)


def test_removeStaleRequests_keeps_session_of_game_still_being_played(engine_monkeypatch, settings_monkeypatch, monkeypatch):
    ms = MatchmakingService()
    sessionId = _createFulfilledDuelRequestWithOldSession(ms)

    # One player disconnected mid game, so the session went back to WAITING_FOR_PLAYERS,
    # but the other player is still in the game and the game loop is running.
    with Session(matchmaking_module.engine) as dbSession:
        gameSessionInfo = dbSession.get(GameSessionInfo, sessionId)
        assert gameSessionInfo != None
        gameSessionInfo.state = GameSessionState.WAITING_FOR_PLAYERS
        dbSession.add(gameSessionInfo)
        dbSession.commit()

    monkeypatch.setitem(
        manager.games,
        sessionId,
        InitializedGameSession(game_session_info=gameSessionInfo, game_loop_running = True)
    )

    ms.removeStaleRequests()

    # Both MatchmakingRequests are gone...
    assert len(ms.requests.values()) == 0

    # ...but the session of the game that is still being played is not.
    assert _readGameSessionInfo(sessionId) != None


def test_removeStaleRequests_keeps_session_of_finished_game(engine_monkeypatch, settings_monkeypatch, monkeypatch):
    ms = MatchmakingService()
    sessionId = _createFulfilledDuelRequestWithOldSession(ms)

    with Session(matchmaking_module.engine) as dbSession:
        gameSessionInfo = dbSession.get(GameSessionInfo, sessionId)
        assert gameSessionInfo != None
        gameSessionInfo.state = GameSessionState.FINISHED
        dbSession.add(gameSessionInfo)
        dbSession.commit()

    monkeypatch.setitem(
        manager.games,
        sessionId,
        InitializedGameSession(game_session_info=gameSessionInfo, game_loop_running = False)
    )

    ms.removeStaleRequests()

    assert len(ms.requests.values()) == 0

    # The finished session is kept, as it is needed for the match history.
    gameSessionInfo = _readGameSessionInfo(sessionId)
    assert gameSessionInfo != None
    assert gameSessionInfo.state == GameSessionState.FINISHED


def test_removeStaleRequests_still_removes_session_of_match_that_never_started(engine_monkeypatch, settings_monkeypatch, monkeypatch):
    ms = MatchmakingService()
    sessionId = _createFulfilledDuelRequestWithOldSession(ms)

    # Nobody ever connected, so the session is a leftover that may be removed.
    ms.removeStaleRequests()

    assert len(ms.requests.values()) == 0
    assert _readGameSessionInfo(sessionId) == None
