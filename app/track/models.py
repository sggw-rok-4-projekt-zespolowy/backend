import uuid

from sqlmodel import Field, SQLModel


class Track(SQLModel, table=True):
    track_id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    deezer_track_id: str = Field(unique=True)
    title: str = Field(max_length=256)
    artist: str | None = Field(default=None, max_length=256)
    album_title: str | None = Field(default=None, max_length=256)
    genre: str | None = Field(default=None, max_length=256)
    year: int = Field(gt=1800, lt=2100)
    preview_url: str = Field(default=None)
    image_url: str | None = Field(default=None)
    backup_image_url: str | None = Field(default=None)
