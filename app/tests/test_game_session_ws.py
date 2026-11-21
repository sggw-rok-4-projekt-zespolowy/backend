import pytest
from app.main import app
from app.models.user import *
from app.models.game_session import *
from app.models.track import *
from app.database import get_session
from app.services.game import GameConnectionManager
from app.utils.crud import create_game_session_info, create_user, delete_track_by_deezer_id, read_user_by_username
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, StaticPool, SQLModel

"""
Unit and integration tests
"""

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)

@pytest.fixture(name="engine_monkeypatch")
def engine_monkeypatch(monkeypatch):
    global engine
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr("app.services.game.engine", engine)

@pytest.fixture(name="session", scope="module")
def session_fixture():
    global engine
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client", scope="module")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="regular_user", scope="module")
def regular_user_data_fixture(session: Session, client: TestClient) -> UserPublic:
    user = read_user_by_username(session, username="regular_user")
    if not user:
        create_user(
            session,
            email="user@example.com",
            username="regular_user",
            password="password",
            role=USER_ROLE.REGULAR_USER
        )

    post_response = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "password"}
    )

    data = post_response.json()["user"]
    return UserPublic.model_validate(data)

@pytest.fixture(name="regular_token", scope="module")
def regular_token_fixture(session: Session, client: TestClient):
    user = read_user_by_username(session, username="regular_user")
    if not user:
        create_user(
            session,
            email="user@example.com",
            username="regular_user",
            password="password",
            role=USER_ROLE.REGULAR_USER
        )

    post_response = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "password"}
    )

    data = post_response.json()["access_token"]
    return data

@pytest.fixture(name="seed_tracks")
def seed_tracks_fixture(session: Session, client: TestClient):
    for deezer_track_id in ["3135556", "906554", "916424", "128743581"]:
        client.post("/track", json={"deezer_track_id": deezer_track_id}, timeout=30)
    yield
    for deezer_track_id in ["3135556", "906554", "916424", "128743581"]:
        delete_track_by_deezer_id(session, deezer_track_id)

def test_connection_request_acknowledgment_is_sent(client: TestClient):
    with client.websocket_connect("/game/000/000") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"

    with client.websocket_connect("/game/a/a") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"

def test_non_existent_game_session_connection_is_rejected(client: TestClient):
    with client.websocket_connect("/game/000/000") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Couldn't find the game session"

def test_finished_game_session_connection_is_rejected(client: TestClient, session: Session):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = ["1"],
                state = GameSessionState.FINISHED
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/1") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Cannot start game session which has state FINISHED"

def test_no_access_token_connection_is_rejected(client: TestClient, session: Session):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = ["1"],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/1") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "'access_token' incorrect or missing for player with id: 1"

def test_incorrect_access_token_connection_is_rejected(client: TestClient, session: Session, regular_user: User):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == f"'access_token' incorrect or missing for player with id: {regular_user.id}"

def test_connection_rejected_if_no_tracks_in_db(client: TestClient, session: Session, regular_user: User, regular_token: str):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == f"No tracks in the database. Add some tracks first"

def test_correct_access_token_connection_is_accepted(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"

def test_uninitialized_game_session_returns_false(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    # Unit test
    gcm = GameConnectionManager()

    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    assert gcm.isGameSessionInitialized(game_session_info.session_id) == False

def test_initialized_game_session_returns_true(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    # Unit test
    gcm = GameConnectionManager()

    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    gcm.initializeGameSession(session, game_session_info.session_id)
    assert gcm.isGameSessionInitialized(game_session_info.session_id) == True

def test_game_session_initialization_acknowledgment_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"

def test_disconnect_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"

def test_connect_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"

def test_reconnect_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Reconnected player with id: {regular_user.id}"

def test_player_state_message_answering_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"

@pytest.mark.timeout(10)
def test_player_message_acknowledgment_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        websocket.send_json({ "text": "Hello World!" })
        data = websocket.receive_text()
        assert data == 'Server received message: {"text":"Hello World!"}'

@pytest.mark.timeout(10)
def test_player_message_invalid_json_message_error_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        websocket.send_text( "text" )
        data = websocket.receive_text()
        assert data == 'Server received message: text'
        data = websocket.receive_text()
        assert "Invalid JSON" in data

@pytest.mark.timeout(10)
def test_player_message_missing_answer_key_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        websocket.send_json({ "text": "Hello World!" })
        data = websocket.receive_text()
        assert data == 'Server received message: {"text":"Hello World!"}'
        data = websocket.receive_text()
        assert "answer" in data and "Field required" in data

@pytest.mark.timeout(10)
def test_player_message_not_an_integer_answer_key_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        websocket.send_json({ "answer": "Hello World!" })
        data = websocket.receive_text()
        assert data == 'Server received message: {"answer":"Hello World!"}'
        data = websocket.receive_text()
        assert "answer" in data and "Input should be a valid integer" in data

@pytest.mark.timeout(10)
def test_round_finishing_message_is_sent(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS,
                seconds_per_round = 5
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        data = websocket.receive_text()
        assert data == f"Round number 1 finished"

@pytest.mark.timeout(20)
def test_next_round_starts_automatically(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS,
                seconds_per_round = 5
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        data = websocket.receive_text()
        assert data == f"Round number 1 finished"
        data = websocket.receive_text()
        assert data == f"Round number 2 starting"

@pytest.mark.timeout(40)
def test_all_rounds_time_out_and_game_finishes(client: TestClient, session: Session, regular_user: User, regular_token: str, seed_tracks, engine_monkeypatch):
    game_session_info = create_game_session_info(
            session,
            GameSessionInfo(
                players_ids = [regular_user.id],
                registered = True,
                state = GameSessionState.WAITING_FOR_PLAYERS,
                seconds_per_round = 5,
                rounds = 3
            )
    )

    with client.websocket_connect(f"/game/{game_session_info.session_id}/{regular_user.id}?access_token={regular_token}") as websocket:
        data = websocket.receive_text()
        assert data == "Received WS connection request"
        data = websocket.receive_text()
        assert data == "Received WS connection request is valid"
        data = websocket.receive_text()
        assert data == "Game session is initialized"
        data = websocket.receive_text()
        assert data == f"Connected player with id: {regular_user.id}"
        data = websocket.receive_text()
        assert data == f"Player state is: ANSWERING"
        data = websocket.receive_text()
        assert data == f"Game session state is: PLAYING"
        data = websocket.receive_text()
        assert data == f"Round number 1 starting"
        websocket.receive_text()
        data = websocket.receive_text()
        assert data == f"Round number 1 finished"
        data = websocket.receive_text()
        assert data == f"Round number 2 starting"
        websocket.receive_text()
        data = websocket.receive_text()
        assert data == f"Round number 2 finished"
        data = websocket.receive_text()
        assert data == f"Round number 3 starting"
        websocket.receive_text()
        data = websocket.receive_text()
        assert data == f"Round number 3 finished"
        data = websocket.receive_text()
        assert data == f"Game session state is: FINISHED"
        data = websocket.receive_text()
        assert data == f"Game session state saved to database"
        websocket.receive_text()

