from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import create_tables

from .audio.routes import router as audio_router
from .auth.routes import router as auth_router
from .cover.routes import router as cover_router
from .game.routes import router as game_router
from .track.routes import router as track_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup: Create tables (for development)
    await create_tables()
    # ## FOR DEBUG. REMOVE IN PROD:
    # import debugpy
    # debugpy.listen(5678)
    ##
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# Configure CORS to allow credentials from frontend
app.add_middleware(
    CORSMiddleware,
    #    allow_origins=[settings.FRONTEND_URL], Use for pdocution
    allow_origins=["*"],
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(audio_router)
app.include_router(auth_router)
app.include_router(cover_router)
app.include_router(game_router)
app.include_router(track_router)


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
