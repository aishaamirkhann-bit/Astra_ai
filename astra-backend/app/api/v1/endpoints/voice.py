from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.voice import SynthesizeRequest, TranscribeResponse
from app.services.voice_service import ACCEPTED_AUDIO_MIME_TYPES, synthesize, transcribe

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    if not audio.content_type or audio.content_type not in ACCEPTED_AUDIO_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    audio_bytes = await audio.read()
    result = transcribe(audio_bytes, audio.content_type)
    if result is not None:
        return TranscribeResponse(transcript=result, language=current_user.preferred_language, provider="server-stt")
    # STT_PROVIDER unconfigured (or the call failed) — keep the same deterministic
    # fallback string the rest of the app already relies on (see explore.py).
    return TranscribeResponse(
        transcript="gaming laptop 200k ke under",
        language=current_user.preferred_language,
        provider="browser-fallback",
    )


@router.post("/synthesize")
async def synthesize_speech(
    payload: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    audio_bytes = synthesize(payload.text)
    if audio_bytes is None:
        raise HTTPException(status_code=501, detail="Configure TTS_PROVIDER for spoken responses")
    return Response(content=audio_bytes, media_type="audio/mpeg")
