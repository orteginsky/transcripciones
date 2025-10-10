# src/api/routes/audio_pipeline.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.cloud import storage
import tempfile
from pathlib import Path

from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.transcription.merge_transcriptions_in_memory import merge_transcriptions_in_memory
from src.ingestion.audio_processor import split_wav_chunks_with_overlap
from src.storage.upload_service import save_drive_audio_to_gcs
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files
from src.docs.google_docs_quick import create_oauth_google_doc
from src.logging_conf import get_logger
from src.settings import GCS_BUCKET

logger = get_logger(__name__)
router = APIRouter()

class AudioRequest(BaseModel):
    case_id: str
    title: str
    audio_link: str
    bucket_name: str | None = None

class TranscriptionResponse(BaseModel):
    case_id: str
    link_doc: str

@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe_audio(request: AudioRequest):
    try:
        logger.info("🚀 Iniciando pipeline para %s", request.case_id)

        # 1️⃣ Subir audio a GCS desde Drive
        gcs_mp3_uri = save_drive_audio_to_gcs(request.audio_link, request.case_id)

        # 2️⃣ Normalizar y convertir a WAV
        bucket_name = request.bucket_name or GCS_BUCKET
        gcs_wav_uri = normalize_and_upload_gcs(gcs_mp3_uri, request.case_id, bucket_name)

        # 3️⃣ Descargar WAV temporalmente
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob_path = gcs_wav_uri.replace(f"gs://{bucket_name}/", "")
        blob = bucket.blob(blob_path)
        title = request.title

        with tempfile.TemporaryDirectory() as tmpdir:
            local_wav = Path(tmpdir) / f"{request.case_id}_16k.wav"
            blob.download_to_filename(local_wav)

            # 4️⃣ Dividir en chunks con solapamiento y transcribir
            chunks_info = split_wav_chunks_with_overlap(local_wav)  # [(chunk_path, start_ms), ...]
            transcript_chunks = [transcribe_audio_chunk(chunk_path) for chunk_path, _ in chunks_info]

            # 5️⃣ Unir transcripciones en memoria
            chunks_for_merge = [(text, start_ms) for text, (_, start_ms) in zip(transcript_chunks, chunks_info)]
            transcription_text = merge_transcriptions_in_memory(chunks_for_merge)

            # 6️⃣ Crear el documento de Google Docs
            resultado = create_oauth_google_doc(title=title, content=transcription_text)

        # 7️⃣ Eliminar archivos temporales del bucket
        deleted_files = delete_gcs_files([gcs_mp3_uri, gcs_wav_uri])
        logger.info(f"Se han eliminado los siguientes archivos: {deleted_files}")
        logger.info("✅ Pipeline completado para %s", request.case_id)

        return TranscriptionResponse(case_id=request.case_id, link_doc=resultado["url"])

    except Exception as e:
        logger.exception("❌ Error en pipeline de transcripción: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
