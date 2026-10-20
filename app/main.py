from app.config import settings
from app.routes.audio import router as audio_router
from app.routes.auth import router as auth_router
from app.routes.cover import router as cover_router
from app.routes.game import router as game_router
from app.routes.track import router as track_router

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
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
