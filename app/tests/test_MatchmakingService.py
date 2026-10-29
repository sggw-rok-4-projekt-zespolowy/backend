import pytest
from app.models.game_session import GameSessionInfoCreate, GameSessionVariant
from app.services.matchmaking import MatchmakingService
from datetime import timedelta
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


def test_createRequest_creates_valid_request(engine_monkeypatch):
    ms = MatchmakingService()

    request = ms.createRequest(
            requestOwnerId = 1,
            requestedGameSessionInfo = GameSessionInfoCreate() # GameSessionInfo with defaults
        )

    assert request.requestOwnerId == 1
    assert request.requestedGameSessionInfo.rounds == 7


def test_createRequest_finds_existing_request_by_owner(engine_monkeypatch):
    ms = MatchmakingService()

    ms.createRequest(
            requestOwnerId = 1,
            requestedGameSessionInfo = GameSessionInfoCreate() # GameSessionInfo with defaults
        )

    request = ms.findRequestByOwner(
            requestOwnerId = 1
        )

    assert request != None
    assert request.requestOwnerId == 1
    assert request.requestedGameSessionInfo.rounds == 7


def test_createRequest_fulfills_request_if_conditions_met(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 1,
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 2,
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 3,
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    sleep(1)

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 4,
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
    assert [1, 3] == requestsMade[0].createdGameSessionInfo.players_ids

def test_createRequest_fulfills_request_if_conditions_met_singleplayer(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 1,
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.SINGLE)
        )
    )

    requestFulfilled = ms.fulfillRequest(requestsMade[0])

    assert requestFulfilled == True
    assert requestsMade[0].fulfilled == True
    assert requestsMade[0].createdGameSessionInfo != None
    assert [1] == requestsMade[0].createdGameSessionInfo.players_ids

def test_createRequest_removes_stale_request_when_appropriate(engine_monkeypatch):
    ms = MatchmakingService()

    requestsMade = []

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 1,
            requestedGameSessionInfo = GameSessionInfoCreate(rounds = 5, variant=GameSessionVariant.DUEL)
        )
    )

    requestsMade.append(
        ms.createRequest(
            requestOwnerId = 2,
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
                requestOwnerId = 1,
                requestedGameSessionInfo = GameSessionInfoCreate(rounds = 7, variant=GameSessionVariant.DUEL)
            )
        )

    assert len(ms.requests.values()) == 2

    sleep(7)

    if ms.isRequestStale(
            requestsMade[0],
            timedelta(seconds=5)
        ):
        ms.deleteRequest(requestsMade[0])

    assert len(ms.requests.values()) == 0
