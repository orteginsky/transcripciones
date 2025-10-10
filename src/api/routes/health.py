from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}
#src/api/routes/audio_routes.py
from fastapi import APIRouter, HTTPException
from src.domain.schemas import AudioRequest, AudioResponse
from src.orchestration.runner import run_audio_from_url
from src.logging_conf import get_logger

router = APIRouter(prefix="", tags=["audio"])
logger = get_logger(__name__)

@router.post("/process-audio", response_model=AudioResponse)
def process_audio(req: AudioRequest):
    try:
        logger.info("Procesando caso=%s url=%s", req.case_id, req.audio_url)
        transcript = run_audio_from_url(
            audio_url=str(req.audio_url),
            case_id=req.case_id,
            client_name=req.client_name,
            visa_type=req.visa_type
        )
        return AudioResponse(status="success", case_id=req.case_id, transcript=transcript)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error procesando case_id=%s", req.case_id)
        raise HTTPException(status_code=500, detail=str(e))
