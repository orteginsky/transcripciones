from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.storage.upload_service import save_drive_audio_to_gcs
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files
from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.docs.google_docs_quick import create_oauth_google_doc
from src.logging_conf import get_logger
from src.settings import GCS_BUCKET

from pathlib import Path
from google.cloud import storage
import tempfile

logger = get_logger(__name__)
router = APIRouter()


# --- 📦 Schemas ---
class AudioRequest(BaseModel):
    case_id: str
    client: str
    witness: str
    date_call: str
    audio_link: str
    bucket_name: str | None = None


class TranscriptionResponse(BaseModel):
    case_id: str
    link_doc: str

# --- 🎙️ Pipeline principal ---
@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe_audio(request: AudioRequest):
    """
    Flujo completo:
    1. Descargar MP3 desde Drive
    2. Subir a GCS
    3. Convertir a WAV 16kHz
    4. Transcribir con Gemini
    5. Eliminar archivos temporales del bucket
    6. Retornar resultado JSON
    """
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
        title= f"Transcription from case id:{request.case_id} to client: {request.client} to witness: {request.witness} at date:{request.date_call}"
        with tempfile.TemporaryDirectory() as tmpdir:
            local_wav = Path(tmpdir) / f"{request.case_id}_16k.wav"
            blob.download_to_filename(local_wav)

            # 4️⃣ Transcribir con Gemini
            transcription_text = transcribe_audio_chunk(local_wav)
            resultado = create_oauth_google_doc(title= title, content= transcription_text)
        
        # 5️⃣ Eliminar archivos temporales del bucket
        deleted_files = delete_gcs_files([gcs_mp3_uri, gcs_wav_uri])

        logger.info(f"Se han eliminado lo siguientes archivos {deleted_files}")
        logger.info("✅ Pipeline completado para %s", request.case_id)

        link=resultado['url']

        return TranscriptionResponse(
            case_id=request.case_id,
            link_doc= link
        )

    except Exception as e:
        logger.exception("❌ Error en pipeline de transcripción: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
