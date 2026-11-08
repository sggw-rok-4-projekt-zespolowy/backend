from pydantic import BaseModel
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4


class BaseTrack(SQLModel):
    album_title: str | None = Field(default=None, max_length=256)
    artist: str | None = Field(default=None, max_length=256)
    backup_image_url: str | None = Field(default=None)
    deezer_track_id: str
    genre: str | None = Field(default=None, max_length=256)
    image_url: str | None = Field(default=None)
    preview_url: str = Field(default=None)
    title: str = Field(max_length=256)
    year: int = Field(gt=1800, lt=2100)
    # None = shared track used in games; otherwise visible only on the owner's profile
    owner_id: int | None = Field(default=None, foreign_key="user.id", index=True)


class Track(BaseTrack, table=True):
    __table_args__ = (UniqueConstraint("deezer_track_id", "owner_id"),)

    track_id: UUID = Field(primary_key=True, default_factory=uuid4)


class TrackCreate(BaseTrack):
    pass


class TrackCreateFromDeezer(BaseModel):
    deezer_track_id: str


class TrackPublic(BaseTrack):
    track_id: UUID
