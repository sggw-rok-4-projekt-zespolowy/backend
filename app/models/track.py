from pydantic import BaseModel
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel
from uuid import uuid4


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
    owner_id: str | None = Field(default=None, foreign_key="user.id", index=True)

# Alembic migration fix
BaseTrack.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Track(BaseTrack, table=True):
    __table_args__ = (UniqueConstraint("deezer_track_id", "owner_id", name="owner_id_constraint"),)
    track_id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))


class TrackCreate(BaseTrack):
    pass


class TrackCreateFromDeezer(BaseModel):
    deezer_track_id: str


class TrackPublic(BaseTrack):
    track_id: str
