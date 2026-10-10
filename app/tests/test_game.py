import pytest

from app.main import app
from app.database import get_db
from fastapi.testclient import TestClient
from sqlmodel import StaticPool, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture(name="session", scope="module")
async def session_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

@pytest.fixture(name="client", scope="module")
async def client_fixture(session: AsyncSession):
    def get_session_override():
        yield session

    app.dependency_overrides[get_db] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_auth_register_successfully_creates_new_user(client: TestClient):
    global existing_user_id
    global token
    post_response = client.post("/auth/register", json={"email": "test@test.com", "password": "password123", "username": "test_user"})
    assert post_response.status_code == 200
    assert post_response.json()["user"]["email"] == "test@test.com"
    existing_user_id = post_response.json()["user"]["id"]
    token = post_response.json()["access_token"]

@pytest.mark.anyio
async def test_auth_me_user_data_contains_score(client: TestClient):
    global token
    post_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert post_response.status_code == 200
    assert post_response.json()["score"] == 0

@pytest.mark.anyio
async def test_auth_register_successfully_creates_another_new_user(client: TestClient):
    global existing_user_id
    global second_token
    post_response = client.post("/auth/register", json={"email": "test2@test.com", "password": "password123", "username": "test2_user"})
    assert post_response.status_code == 200
    assert post_response.json()["user"]["email"] == "test2@test.com"
    existing_user_id = post_response.json()["user"]["id"]
    second_token = post_response.json()["access_token"]

@pytest.mark.anyio
async def test_registered_start_successfully_initiates_session_creation(client: TestClient):
    global token
    post_response = client.post("/game/registered-start", headers={"Authorization": f"Bearer {token}"}, json={"variant": "DUEL"})
    assert post_response.status_code == 202

@pytest.mark.anyio
async def test_registered_start_successfully_creates_a_game_session(client: TestClient):
    global second_token
    global registered_session_id
    post_response = client.post("/game/registered-start", headers={"Authorization": f"Bearer {second_token}"}, json={"variant": "DUEL"})
    assert post_response.status_code == 200
    assert post_response.json()["variant"] == "DUEL"
    registered_session_id = post_response.json()["session_id"]

@pytest.mark.anyio
async def test_quick_start_returns_a_session_successfully(client: TestClient):
    global quick_start_session_id
    global quick_start_session_player_id
    post_response = client.post("/game/quick-start", json={"variant": "SINGLE"})
    assert post_response.status_code == 200
    assert post_response.json()["variant"] == "SINGLE"
    quick_start_session_id = post_response.json()["session_id"]
    quick_start_session_player_id = post_response.json()["players_ids"][0]
