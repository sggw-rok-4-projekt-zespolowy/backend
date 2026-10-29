from app.config import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from os import makedirs, path

router = APIRouter(prefix="/audio")

makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.get("/{filename}")
async def create_track(filename: str) -> FileResponse:
    file_location = path.join(settings.UPLOAD_DIR, filename)
    if not path.exists(file_location):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        path=file_location,
        media_type="audio/mpeg",
        filename=path.basename(file_location),
    )
