# src/api/routes/audio_pipeline.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from src.domain.schemas import TranscriptionRequest, TranscriptionResponse, ErrorResponse
from src.orchestration.runner import run_transcription_pipeline_to_doc, PipelineError

router = APIRouter()

@router.post("/transcribe",
             response_model=TranscriptionResponse,
             responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
def transcribe_to_doc(
    req: TranscriptionRequest,
    x_transcriber: str | None = Header(default=None),
):
    media_link = req.media_link or req.audio_link
    if not media_link:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "media_link (o audio_link) es requerido."})
    if not req.doc_id:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "doc_id es requerido."})
    transcriber_override = x_transcriber or req.transcriber
    try:
        out = run_transcription_pipeline_to_doc(
            case_id=req.case_id,
            title=req.title,
            media_link=media_link,
            doc_id=req.doc_id,
            language_code=req.language_code,
            transcriber_override=transcriber_override,
        )
        return out
    except PipelineError as e:
        status = 500
        if e.code in ("BAD_REQUEST", "AUTH_ERROR", "NOT_FOUND"):
            status = 400
        elif e.code in ("PROHIBITED_CONTENT",):
            status = 422
        raise HTTPException(status_code=status, detail={"code": e.code, "message": str(e), "details": e.details})
