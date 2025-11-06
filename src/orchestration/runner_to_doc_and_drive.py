# src/orchestration/runner_to_doc_and_driver.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import PurePosixPath

from google.cloud import storage
import time

from src.metrics import TRANSCRIPTIONS_TOTAL, TRANSCRIPTIONS_ERRORS_TOTAL, PIPELINE_DURATION_SECONDS, STT_PHASE_SECONDS
from src.docs.google_docs_service import append_formatted_transcript
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files
from src.storage.upload_service import save_drive_audio_to_gcs
from src.transcription.transcribers import transcribe_from_gcs_uri
from src.transcription.gemini_vertex_transcriber import gemini_vertex_transcribe_gcs
from src.storage.drive_text_saver import save_transcript_txt_to_drive

from src.logging_conf import get_logger
from src.settings import GCS_BUCKET, get_settings

logger = get_logger(__name__)

ALLOWED_TRANSCRIBERS = {"gemini_vertex", "stt_v2"}

class PipelineError(RuntimeError):
    code: str = "INTERNAL"
    def __init__(self, message: str, code: str = "INTERNAL", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

def run_transcription_pipeline_to_doc_and_drive(
    *,
    case_id: str,
    title: str,
    media_link: str,
    doc_id: str,
    drive_folder_id: str,                 # 👈 requerido en este runner
    language_code: Optional[str] = None,
    bucket_name: Optional[str] = None,
    transcriber_override: Optional[str] = None,
) -> Dict[str, Any]:
    start = time.time()
    logger.info("🚀 Pipeline->Doc+Drive | case_id=%s doc_id=%s folder_id=%s", case_id, doc_id, drive_folder_id)
    s = get_settings()

    bucket_name = bucket_name or GCS_BUCKET
    if not bucket_name:
        raise PipelineError("GCS_BUCKET vacío.", code="BAD_REQUEST")

    backend = (transcriber_override or (s.transcriber or "stt_v2")).lower().strip()
    if backend not in ALLOWED_TRANSCRIBERS:
        raise PipelineError(f"Transcriber no soportado: '{backend}'", code="BAD_REQUEST")
    language_code = (language_code or s.stt_language_code or "es-ES")

    storage_client = storage.Client()
    uris_creados: List[str] = []

    try:
        # 1) Drive -> GCS
        gcs_media_uri = save_drive_audio_to_gcs(media_link, case_id)
        uris_creados.append(gcs_media_uri)
        logger.info("📤 Media subido a GCS: %s", gcs_media_uri)

        # 2) Seleccionar input según backend
        if backend == "gemini_vertex":
            gcs_input_uri = gcs_media_uri     # MP3 directo
            input_mime = "audio/mpeg"
            logger.info("⏭️ Gemini usará MP3 directo (sin normalización).")
        else:
            gcs_input_uri = normalize_and_upload_gcs(
                gcs_media_uri, case_id, bucket_name, target_format="flac", auto_sr=True
            )
            uris_creados.append(gcs_input_uri)
            input_mime = "audio/flac"
            logger.info("🎛️ Audio normalizado a FLAC: %s", gcs_input_uri)

        # 3) Transcribir
        logger.info("📝 Transcribiendo con backend=%s | lang=%s…", backend, language_code)
        prompt_text = getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
        transcription_text: str = ""

        stt_start = time.time()
        try:
            if backend == "gemini_vertex":
                transcription_text = gemini_vertex_transcribe_gcs(
                    gcs_input_uri, prompt=prompt_text, mime_type=input_mime
                )
                logger.info("Se utilizó Gemini (Vertex).")
            else:
                transcription_text = transcribe_from_gcs_uri(gcs_input_uri, language_code=language_code)
                logger.info("Se utilizó Speech-to-Text v2.")
        finally:
            STT_PHASE_SECONDS.labels(backend=backend).observe(time.time() - stt_start)

        if not transcription_text.strip():
            raise PipelineError("La transcripción resultó vacía o nula.", code="STT_FAILED")

        # 4) Guardar .txt en GCS (igual que tu runner base)
        try:
            _, key = gcs_input_uri.replace("gs://", "").split("/", 1)
        except ValueError:
            key = "transcription"
        stem = PurePosixPath(key).stem

        txt_blob_path = f"transcripts/{case_id}/{stem}_transcription.txt"
        bucket = storage_client.bucket(bucket_name)
        bucket.blob(txt_blob_path).upload_from_string(transcription_text, content_type="text/plain")
        logger.info("🧾 Transcripción guardada en GCS: gs://%s/%s", bucket_name, txt_blob_path)

        # 5) Insertar en Google Doc (formato)
        append_formatted_transcript(doc_id=doc_id, title=title, transcript_text=transcription_text)
        logger.info("📄 Transcripción insertada en Doc %s", doc_id)

        # 6) NUEVO: Guardar .txt en Google Drive (carpeta del request)
        drive_info = save_transcript_txt_to_drive(
            text=transcription_text,
            case_id=case_id,
            folder_id=drive_folder_id,
            title=title,
        )

        # 7) Limpieza temporales
        _ = delete_gcs_files(uris_creados)
        logger.info("🧹 Temporales GCS eliminados.")

        duration = time.time() - start
        PIPELINE_DURATION_SECONDS.observe(duration)
        TRANSCRIPTIONS_TOTAL.labels(backend=backend).inc()

        result = {
            "case_id": case_id,
            "title": title,
            "backend": backend,
            "doc_id": doc_id,
            "gcs_txt_path": f"gs://{bucket_name}/{txt_blob_path}",
            "drive_txt": drive_info,  # {file_id, webViewLink, name}
            "duration_ms": int(duration * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("✅ Pipeline->Doc+Drive completado | case_id=%s | duration_ms=%s", case_id, result["duration_ms"])
        return result

    except PipelineError as e:
        TRANSCRIPTIONS_ERRORS_TOTAL.labels(code=e.code).inc()
        raise
    except Exception:
        TRANSCRIPTIONS_ERRORS_TOTAL.labels(code="INTERNAL").inc()
        raise
