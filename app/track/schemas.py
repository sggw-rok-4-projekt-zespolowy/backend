import uuid

from pydantic import BaseModel, ConfigDict


class TrackPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: uuid.UUID
    artist: str | None
    album_title: str | None
    genre: str | None
    year: int
    preview_url: str | None
    image_url: str | None
    backup_image_url: str | None
    title: str


class TrackCreate(BaseModel):
    deezer_track_id: str


class TrackPrivate(BaseModel):
    track_id: uuid.UUID
