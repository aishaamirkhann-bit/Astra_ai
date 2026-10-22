"""Authenticated, read-only multimodal room styling endpoint."""
import asyncio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.spatial_decorator import build_spatial_decor_bundle
from app.services.vision import analyze_room_image, sniff_image_type
from app.services.localization import detect_locale

router = APIRouter(prefix="/spatial-decorator", tags=["Spatial Decorator"])
MAX_ROOM_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("/recommendations")
async def recommend_room_decor(
    image: UploadFile = File(...),
    message: str = Form(default="", max_length=1000),
    locale: str | None = Form(default=None, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return visual room cues and advisory catalog matches; this route writes nothing."""
    content_type = image.content_type or ""
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP room photo.")
    image_bytes = await image.read(MAX_ROOM_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_ROOM_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Room photo must be 8 MB or smaller.")
    if not sniff_image_type(image_bytes):
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid supported image.")
    detected_locale = detect_locale(message)
    active_locale = detected_locale if detected_locale != "en" else detect_locale("", locale or current_user.preferred_language)
    room_attributes = await asyncio.to_thread(analyze_room_image, image_bytes, active_locale)
    return build_spatial_decor_bundle(
        db, image_bytes, message, active_locale, current_user.country or "PK", room_attributes or {},
    )
