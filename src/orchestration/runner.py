# src/orchestration/runner.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from google.cloud import storage

from src.docs.google_docs_quick import create_oauth_google_doc
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files, delete_gcs_docx_files
from src.storage.upload_service import save_drive_audio_to_gcs
from src.transcription.transcribers import (
    transcribe_from_gcs_uri,
    stt_v2_transcribe_gcs_lro,
)
from src.transcription.gemini_vertex_transcriber import gemini_vertex_transcribe_gcs

from src.logging_conf import get_logger
from src.settings import GCS_BUCKET, get_settings

logger = get_logger(__name__)


class PipelineError(RuntimeError):
    """Errores controlados del pipeline."""


def run_transcription_pipeline(
    *,
    case_id: str,
    title: str,
    audio_link: str,
    docs_link: str,
    lenguage: str, 
    bucket_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pipeline GCS-directo:
      1️⃣ Sube MP3 desde Drive a GCS
      2️⃣ Normaliza y convierte a WAV 16k en GCS
      3️⃣ Transcribe desde GCS (Gemini o STT v2, según settings)
      4️⃣ Guarda la transcripción en GCS (.txt)
      5️⃣ Crea Google Doc
      6️⃣ Limpia archivos temporales de GCS
    """
    logger.info("🚀 Iniciando pipeline de audio | case_id=%s", case_id)

    bucket_name = bucket_name or GCS_BUCKET
    if not bucket_name:
        raise PipelineError("No se definió bucket_name y GCS_BUCKET está vacío.")

    s = get_settings()
    backend = (s.transcriber or "stt_v2").lower()
    storage_client = storage.Client()

    uris_creados: List[str] = []

    try:
        # 1️⃣ MP3 → GCS
        gcs_mp3_uri = save_drive_audio_to_gcs(audio_link, case_id)
        uris_creados.append(gcs_mp3_uri)
        logger.info("📤 MP3 subido a GCS: %s", gcs_mp3_uri)

        # 2️⃣ Normalizar → WAV16k en GCS
        gcs_wav_uri = normalize_and_upload_gcs(gcs_mp3_uri, case_id, bucket_name)
        uris_creados.append(gcs_wav_uri)
        logger.info("🎛️ WAV normalizado a GCS: %s", gcs_wav_uri)

        # 3️⃣ Transcribir DIRECTO desde GCS
        logger.info("📝 Transcribiendo desde GCS con backend=%s…", backend)

        prompt_text = getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
        transcription_text: str = ""

        try:
            # Gemini → pasa prompt explícito
            if backend == "gemini_vertex":
                transcription_text = gemini_vertex_transcribe_gcs(
                    gcs_wav_uri,
                    prompt=getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None),
                )
                logger.info("Se utilizo gemini")
            else:
                transcription_text = transcribe_from_gcs_uri(gcs_wav_uri)
                logger.info("NO se utilizo gemini")

        except Exception as e:
            msg = str(e)
            if backend == "stt_v2" and "maximum of 10485760 bytes" in msg:
                logger.warning(
                    "STT v2 síncrono superó 10 MB. Reintentando con BatchRecognize (LRO)…"
                )
                transcription_text = stt_v2_transcribe_gcs_lro(gcs_wav_uri)
            else:
                raise

        if not transcription_text.strip():
            raise PipelineError("La transcripción resultó vacía o nula.")

        # 4️⃣ Guardar transcripción .txt en GCS
        txt_blob_path = f"transcripts/{case_id}/{Path(gcs_wav_uri).stem}_transcription.txt"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(txt_blob_path)
        blob.upload_from_string(transcription_text, content_type="text/plain")

        gcs_txt_uri = f"gs://{bucket_name}/{txt_blob_path}"
        logger.info("🧾 Transcripción guardada en GCS: %s", gcs_txt_uri)

        # 5️⃣ Crear Google Doc
        doc = create_oauth_google_doc(
            title=title,
            content=transcription_text,
            make_public=True,
        )
        logger.info("📄 Google Doc creado: %s", doc["url"])

        # 6️⃣ Limpieza de GCS (solo MP3/WAV temporales)
        deleted_files = delete_gcs_files(uris_creados)
        logger.info("🧹 Archivos GCS eliminados: %s", deleted_files)
        
        # 🧾 Limpieza adicional de DOCX antiguos
        deleted_docx = delete_gcs_docx_files(bucket_name, prefix="docs/")
        logger.info("🧹 Archivos DOCX eliminados: %s", deleted_docx)
        result = {
            "case_id": case_id,
            "title": title,
            "backend": backend,
            "bucket": bucket_name,
            "gcs_txt_uri": gcs_txt_uri,
            "link_doc": doc["url"],
            "doc_id": doc["doc_id"],
            "created_uris": uris_creados,
            "deleted_uris": deleted_files,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info("✅ Pipeline completado con éxito | case_id=%s", case_id)
        return result

    except Exception as e:
        logger.exception("❌ Error en pipeline | case_id=%s", case_id)
        try:
            if uris_creados:
                delete_gcs_files(uris_creados)
                logger.warning("🧹 Limpieza parcial de GCS tras error.")
        except Exception:
            logger.warning("⚠️ No se pudo limpiar GCS tras el error.")
        raise PipelineError(str(e)) from e
