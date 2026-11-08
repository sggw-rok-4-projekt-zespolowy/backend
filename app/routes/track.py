from app.config import settings
from app.database import SessionDep
from app.models.track import Track, TrackCreate, TrackCreateFromDeezer, TrackPublic
from app.models.user import User, USER_ROLE
from app.utils.dependencies import get_current_user
from collections.abc import Sequence
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from os import makedirs, path
from requests import get
from sqlmodel import select
from typing import Annotated
from uuid import uuid4

router = APIRouter(prefix="/track")

UPLOAD_DIR = settings.UPLOAD_DIR
BASE_URL = settings.BASE_URL
makedirs(UPLOAD_DIR, exist_ok=True)

CurrentUser = Annotated[User, Depends(get_current_user([USER_ROLE.REGULAR_USER]))]


@router.get("", response_model=Sequence[TrackPublic])
async def read_tracks(session: SessionDep) -> Sequence[Track]:
    tracks = session.exec(select(Track).where(Track.owner_id == None)).all()
    return tracks


@router.get("/mine", response_model=Sequence[TrackPublic])
async def read_my_tracks(session: SessionDep, current_user: CurrentUser) -> Sequence[Track]:
    tracks = session.exec(select(Track).where(Track.owner_id == current_user.id)).all()
    return tracks


@router.post("")
async def create_track(session: SessionDep, track: TrackCreateFromDeezer) -> Track:
    existing = (
        session.exec(
            select(Track).where(
                Track.deezer_track_id == track.deezer_track_id, Track.owner_id == None
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="This track already exists in the database"
        )

    return create_track_from_deezer(session, track.deezer_track_id)


@router.post("/mine", response_model=TrackPublic)
async def create_my_track(
    session: SessionDep, track: TrackCreateFromDeezer, current_user: CurrentUser
) -> Track:
    existing = (
        session.exec(
            select(Track).where(
                Track.deezer_track_id == track.deezer_track_id,
                (Track.owner_id == None) | (Track.owner_id == current_user.id),
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="This track is already on your profile"
        )

    return create_track_from_deezer(session, track.deezer_track_id, current_user.id)


def create_track_from_deezer(
    session: SessionDep, deezer_track_id: str, owner_id: int | None = None
) -> Track:
    res = get(f"https://api.deezer.com/track/{deezer_track_id}")
    if res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't get the track from Deezer"
        )

    res_data = res.json()
    if not res_data.get("preview"):
        raise HTTPException(
            status_code=404, detail="The response from Deezer was not as expected"
        )

    preview_res = get(res_data["preview"])
    if preview_res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't access audio preview from Deezer"
        )

    image_res = get(res_data["album"]["cover_medium"])
    if image_res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't access album cover from Deezer"
        )

    release_date = datetime.strptime(res_data["release_date"], "%Y-%m-%d")

    audio_filename = f"{uuid4()}_{datetime.now().timestamp()}"
    file_location = path.join(UPLOAD_DIR, audio_filename) + ".mp3"
    with open(file_location, "wb") as f:
        f.write(preview_res.content)

    image_filename = f"{uuid4()}_{datetime.now().timestamp()}"
    file_location = path.join(UPLOAD_DIR, image_filename) + ".jpg"
    with open(file_location, "wb") as f:
        f.write(image_res.content)

    new_track = Track.model_validate(
        Track(
            title=res_data["title_short"],
            artist=res_data.get("artist", {}).get("name"),
            album_title=res_data.get("album", {}).get("title"),
            year=release_date.date().year,
            deezer_track_id=deezer_track_id,
            preview_url=f"{BASE_URL}/audio/{audio_filename}.mp3",
            image_url=res_data.get("album", {}).get("cover_medium"),
            backup_image_url=f"{BASE_URL}/cover/{image_filename}.jpg",
            owner_id=owner_id,
        )
    )

    session.add(new_track)
    session.commit()
    session.refresh(new_track)
    return new_track
