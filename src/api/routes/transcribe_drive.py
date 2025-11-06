# src/api/routes/transcribe_driver.py
from __future__ import annotations
from fastapi import APIRouter, Header
from typing import Optional

from src.domain.schemas import TranscribeAndDriveRequest
from src.orchestration.runner_to_doc_and_drive import run_transcription_pipeline_to_doc_and_drive

router = APIRouter()

@router.post("/api/transcribe-and-drive")
def transcribe_and_drive(
    body: TranscribeAndDriveRequest,
    x_transcriber: Optional[str] = Header(default=None),
):
    return run_transcription_pipeline_to_doc_and_drive(
        case_id=body.case_id,
        title=body.title,
        media_link=body.media_link,
        doc_id=body.doc_id,
        drive_folder_id=body.drive_folder_id,          # 👈 del request
        language_code=body.language_code,
        transcriber_override=x_transcriber or body.transcriber,
    )
