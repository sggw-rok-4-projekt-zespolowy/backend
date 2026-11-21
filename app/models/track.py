from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from uuid import uuid4


class BaseTrack(SQLModel):
    album_title: str | None = Field(default=None, max_length=256)
    artist: str | None = Field(default=None, max_length=256)
    backup_image_url: str | None = Field(default=None)
    deezer_track_id: str = Field(unique=True)
    genre: str | None = Field(default=None, max_length=256)
    image_url: str | None = Field(default=None)
    preview_url: str = Field(default=None)
    title: str = Field(max_length=256)
    year: int = Field(gt=1800, lt=2100)


class Track(BaseTrack, table=True):
    track_id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))


class TrackCreate(BaseTrack):
    pass


class TrackCreateFromDeezer(BaseModel):
    deezer_track_id: str


class TrackPublic(BaseTrack):
    track_id: str
