# src/orchestration/runner_to_doc.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from google.cloud import storage

from src.docs.google_docs_service import append_text_to_google_doc
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files
from src.storage.upload_service import save_drive_audio_to_gcs  # tu implementación actual
from src.transcription.transcribers import (
    transcribe_from_gcs_uri,
    stt_v2_transcribe_gcs_lro,  # si ya lo expones; si no, quita el fallback explícito
)
from src.transcription.gemini_vertex_transcriber import gemini_vertex_transcribe_gcs

from src.logging_conf import get_logger
from src.settings import GCS_BUCKET, get_settings

logger = get_logger(__name__)

class PipelineError(RuntimeError):
    code: str = "INTERNAL"
    def __init__(self, message: str, code: str = "INTERNAL", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

def run_transcription_pipeline_to_doc(
    *,
    case_id: str,
    title: str,
    media_link: str,
    doc_id: str,
    language_code: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pipeline que:
      1) Descarga audio (Drive) -> GCS
      2) Normaliza a WAV 16k mono en GCS
      3) Transcribe (backend según settings: gemini_vertex | stt_v2)
      4) Opción: guarda .txt en GCS (interno)
      5) APPEND de la transcripción al Doc 'doc_id'
      6) Limpia temporales GCS
    """
    logger.info("🚀 Pipeline->Doc | case_id=%s doc_id=%s", case_id, doc_id)
    s = get_settings()

    bucket_name = bucket_name or GCS_BUCKET
    if not bucket_name:
        raise PipelineError("GCS_BUCKET vacío.", code="BAD_REQUEST")

    backend = (s.transcriber or "stt_v2").lower()
    language_code = (language_code or s.stt_language_code or "es-ES")

    storage_client = storage.Client()
    uris_creados: List[str] = []

    try:
        # 1) Drive -> GCS (usa tu función actual)
        gcs_media_uri = save_drive_audio_to_gcs(media_link, case_id)
        uris_creados.append(gcs_media_uri)
        logger.info("📤 Media subido a GCS: %s", gcs_media_uri)

        # 2) Normalizar -> WAV16k
        gcs_wav_uri = normalize_and_upload_gcs(gcs_media_uri, case_id, bucket_name)
        uris_creados.append(gcs_wav_uri)
        logger.info("🎛️ WAV normalizado a GCS: %s", gcs_wav_uri)

        # 3) Transcribir según backend
        logger.info("📝 Transcribiendo con backend=%s | lang=%s…", backend, language_code)
        prompt_text = getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
        transcription_text: str = ""

        try:
            if backend == "gemini_vertex":
                transcription_text = gemini_vertex_transcribe_gcs(
                    gcs_wav_uri,
                    prompt=prompt_text,
                )
                logger.info("Se utilizó Gemini (Vertex).")
            else:
                transcription_text = transcribe_from_gcs_uri(gcs_wav_uri, language_code=language_code)
                logger.info("Se utilizó Speech-to-Text v2.")
        except Exception as e:
            msg = str(e)
            if backend == "stt_v2" and ("maximum of 10485760 bytes" in msg or "RESOURCE_EXHAUSTED" in msg):
                logger.warning("STT v2 sync limit. Reintentando con LRO…")
                transcription_text = stt_v2_transcribe_gcs_lro(gcs_wav_uri, language_code=language_code)
            else:
                raise

        if not transcription_text.strip():
            raise PipelineError("La transcripción resultó vacía o nula.", code="STT_FAILED")

        # 4) Guardar .txt en GCS (opcional, útil para auditoría)
        stem = Path(gcs_wav_uri).stem
        txt_blob_path = f"transcripts/{case_id}/{stem}_transcription.txt"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(txt_blob_path)
        blob.upload_from_string(transcription_text, content_type="text/plain")
        logger.info("🧾 Transcripción guardada en GCS: gs://%s/%s", bucket_name, txt_blob_path)

        # 5) APPEND al Doc existente
        append_text_to_google_doc(doc_id=doc_id, content=transcription_text)
        logger.info("📄 Transcripción insertada en Doc %s", doc_id)

        # 6) Limpieza de temporales en GCS
        _ = delete_gcs_files(uris_creados)
        logger.info("🧹 Temporales GCS eliminados.")

        result = {
            "case_id": case_id,
            "title": title,
            "backend": backend,
            "doc_id": doc_id,
            "duration_ms": 0,  # si luego quieres medir, aquí puedes calcular y asignar
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info("✅ Pipeline completado | case_id=%s", case_id)
        return result

    except PipelineError:
        raise
    except Exception as e:
        logger.exception("❌ Error en pipeline | case_id=%s", case_id)
        # Limpieza best-effort
        try:
            if uris_creados:
                delete_gcs_files(uris_creados)
        except Exception:
            pass
        raise PipelineError(str(e), code="INTERNAL")
