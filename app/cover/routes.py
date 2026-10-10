import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(prefix="/cover")

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/{filename}")
async def create_track(filename: str) -> FileResponse:
    file_location = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="Cover image file not found")
    return FileResponse(
        path=file_location,
        media_type="image/jpeg",
        filename=os.path.basename(file_location),
    )
