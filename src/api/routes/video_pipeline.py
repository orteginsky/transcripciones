# src/api/routes/video_pipeline.py
from __future__ import annotations
from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import tempfile
import shutil

from src.logging_conf import get_logger
from src.settings import GCS_BUCKET
from src.ingestion.drive_loader import extract_drive_id, download_from_drive
from src.ingestion.auth_service import get_google_creds_service
from src.ingestion.video_audio import extract_audio_to_mp3
from src.storage.gcs_uploader import upload_to_gcs
from src.orchestration.runner import run_transcription_pipeline_from_gcs  # 👈 función nueva

logger = get_logger(__name__)
router = APIRouter()

class VideoToDocRequest(BaseModel):
    case_id: str
    title: str
    video_link: HttpUrl | str
    doc_id: str
    language_code: str | None = None
    transcriber: str | None = None  # override opcional

@router.post("/transcribe-video")
def transcribe_video(
    req: VideoToDocRequest,
    response: Response,
    x_transcriber: str | None = Header(default=None),
):
    tmpdir = Path(tempfile.mkdtemp(prefix=f"vid2mp3_{req.case_id}_"))
    try:
        # 0) Obtener servicios Google (SA)
        drive_service, docs_service, creds = get_google_creds_service()
        # 1) Descargar video desde Drive
        file_id = extract_drive_id(str(req.video_link))
        video_path = tmpdir / f"{req.case_id}.video"
        download_from_drive(drive_service, file_id, video_path)

        # 2) Extraer audio MP3
        mp3_path = extract_audio_to_mp3(video_path, tmpdir, basename=req.case_id)

        # 3) Subir a GCS
        dest = f"videos_audio/{req.case_id}/{mp3_path.name}"
        gcs_uri = upload_to_gcs(mp3_path, bucket_name=GCS_BUCKET, destination=dest)

        if gcs_uri:
            logger.debug("todo ok gcs_uri tiene algo")
        else:
            logger.debug("nonono gcs_uri no tiene nada, cambialo mi shavo")
            gcs_uri = ""
        
        # 4) Reusar pipeline (desde un audio ya en GCS)
        out = run_transcription_pipeline_from_gcs(
            case_id=req.case_id,
            title=req.title,
            gcs_media_uri=gcs_uri,
            doc_id=req.doc_id,
            language_code=req.language_code,
            transcriber_override=x_transcriber or req.transcriber,
        )
        response.headers["X-Backend"] = out["backend"]
        return out

    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
