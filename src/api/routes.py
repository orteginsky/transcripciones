# src/api/routes.py
"""
API Routes for Transcription Service

Main endpoint: POST /api/transcribe
- Accepts audio (.mp3, .wav, .m4a) and video (.mp4) files from Drive
- Uses intelligent routing to select optimal transcription engine
- Returns transcription result with metadata
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, status

from src.api.schemas import TranscriptionRequest, TranscriptionResponse, ErrorResponse
from src.orchestration.runner import run_transcription_pipeline, PipelineError
from src.logging_conf import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    },
    summary="Transcribe audio or video file",
    description="""
    Transcribe an audio or video file from Google Drive.

    **Supported formats:**
    - Audio: .mp3, .wav, .m4a, .flac
    - Video: .mp4

    **Routing logic (when strategy='auto'):**
    1. If from 8x8 source → STT V1 (stereo phone calls)
    2. If video file (.mp4) → Gemini 2.5 Flash (mono)
    3. If audio is longer than 25 min AND stereo → STT V1 (stereo)
    4. Otherwise → Gemini 2.5 Flash (mono)

    **Normalization:**
    - STT V1: Always normalizes to FLAC stereo
    - Gemini: Only normalizes if necessary (saves processing time)

    **Callbacks:**
    - Optionally updates Google Sheets with result (status, doc link, duration, engine)
    """
)
def transcribe_endpoint(request: TranscriptionRequest):
    """
    Main transcription endpoint.

    Orchestrates the full pipeline:
    1. Download from Drive
    2. Intelligent routing
    3. Conditional normalization
    4. Transcription
    5. Write to Google Docs
    6. Update Google Sheets (if configured)
    """
    logger.info(f"📨 Recibida solicitud de transcripción: case_id={request.case_id}")

    try:
        # Execute pipeline
        result = run_transcription_pipeline(request)

        # Build response
        response = TranscriptionResponse(
            case_id=result["case_id"],
            doc_id=result["doc_id"],
            backend_used=result["backend_display_name"],
            duration_seconds=result["duration_seconds"],
            status="success",
            timestamp=result["timestamp"],
            output_files={
                "google_doc": result["doc_url"]
            }
        )

        logger.info(f"✅ Transcripción exitosa: {request.case_id} → {result['backend_display_name']}")
        return response

    except PipelineError as e:
        logger.error(f"❌ Pipeline error: {e.message}", exc_info=True)
        error_status = status.HTTP_400_BAD_REQUEST if e.code == "BAD_REQUEST" else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(
            status_code=error_status,
            detail=e.message
        )

    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
