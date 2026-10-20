from app.models.track import Track, TrackCreate, TrackCreateFromDeezer, TrackPublic
import os
import uuid
from collections.abc import Sequence
from datetime import datetime

import requests
from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.config import settings
from app.database import SessionDep


router = APIRouter(prefix="/track")

UPLOAD_DIR = settings.UPLOAD_DIR
BASE_URL = settings.BASE_URL
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=Sequence[TrackPublic])
async def read_tracks(session: SessionDep) -> Sequence[Track]:
    tracks = session.exec(select(Track)).all()
    return tracks


@router.post("")
async def create_track(session: SessionDep, track: TrackCreateFromDeezer) -> Track:
    existing = (
        session.exec(
            select(Track).where(Track.deezer_track_id == track.deezer_track_id)
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="This track already exists in the database"
        )

    res = requests.get(f"https://api.deezer.com/track/{track.deezer_track_id}")
    if res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't get the track from Deezer"
        )

    res_data = res.json()
    if "preview" not in res_data:
        raise HTTPException(
            status_code=404, detail="The response from Deezer was not as expected"
        )

    preview_res = requests.get(res_data["preview"])
    if preview_res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't access audio preview from Deezer"
        )

    image_res = requests.get(res_data["album"]["cover_medium"])
    if image_res.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Couldn't access album cover from Deezer"
        )

    release_date = datetime.strptime(res_data["release_date"], "%Y-%m-%d")

    audio_filename = f"{uuid.uuid4()}_{datetime.now().timestamp()}"
    file_location = os.path.join(UPLOAD_DIR, audio_filename) + ".mp3"
    with open(file_location, "wb") as f:
        f.write(preview_res.content)

    image_filename = f"{uuid.uuid4()}_{datetime.now().timestamp()}"
    file_location = os.path.join(UPLOAD_DIR, image_filename) + ".jpg"
    with open(file_location, "wb") as f:
        f.write(image_res.content)

    new_track = Track.model_validate(
        Track(
            title=res_data["title_short"],
            artist=res_data.get("artist", {}).get("name"),
            album_title=res_data.get("album", {}).get("title"),
            year=release_date.date().year,
            deezer_track_id=track.deezer_track_id,
            preview_url=f"{BASE_URL}/audio/{audio_filename}.mp3",
            image_url=res_data.get("album", {}).get("cover_medium"),
            backup_image_url=f"{BASE_URL}/cover/{image_filename}.jpg"
        )
    )

    session.add(new_track)
    session.commit()
    session.refresh(new_track)
    return new_track
