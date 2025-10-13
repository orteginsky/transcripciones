# src/storage/audio_normalizer_service.py

# Librerias externas
from google.cloud import storage

# Librerias internas
import tempfile
from pathlib import Path

# Módulos
from src.ingestion.audio_processor import process_mp3_to_wav16k
from src.storage.gcs_uploader import upload_to_gcs

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def normalize_and_upload_gcs(mp3_gcs_uri: str, case_id: str, bucket_name: str | None) -> str:
    """
    Descarga un MP3 de GCS, lo normaliza a WAV 16kHz mono PCM16, y lo vuelve a subir.
    Retorna la nueva URI gs:// del archivo WAV.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # --- 1️⃣ Parsear ruta GCS ---
    assert mp3_gcs_uri.startswith("gs://"), "La URI debe iniciar con gs://"
    _, path = mp3_gcs_uri.replace("gs://", "").split("/", 1)
    blob = bucket.blob(path)

    # --- 2️⃣ Crear directorio temporal ---
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        local_mp3 = tmpdir_path / f"{case_id}.mp3"
        local_wav = tmpdir_path / f"{case_id}_16k.wav"

        # --- 3️⃣ Descargar MP3 ---
        logger.info("Descargando MP3 desde %s", mp3_gcs_uri)
        blob.download_to_filename(local_mp3)

        # --- 4️⃣ Normalizar y convertir ---
        logger.info("Normalizando y convirtiendo a WAV 16kHz")
        process_mp3_to_wav16k(local_mp3, tmpdir_path, out_name=local_wav.name)

        # --- 5️⃣ Subir WAV al bucket ---
        wav_destination = f"processed/{case_id}_16k.wav"
        wav_uri = upload_to_gcs(local_wav, bucket_name, destination=wav_destination)

        logger.info("Archivo WAV subido: %s", wav_uri)
        return wav_uri
