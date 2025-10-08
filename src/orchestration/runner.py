from src.ingestion.drive_loader import download_from_drive, extract_drive_id
from src.ingestion.audio_processor import process_mp3_to_wav16k, split_wav_chunks
from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.storage.gcs import upload_temp_to_gcs, delete_gcs_blob
from src.ingestion.auth import get_google_creds_service
from src.settings import TEMP_BUCKET, INPUT_DIR, WAV_OUTPUT_DIR
from src.logging_conf import get_logger
import tempfile, os

logger = get_logger(__name__)

def run_audio_from_url(audio_url: str, case_id: str) -> str:
    sheets_service, drive_service, _ = get_google_creds_service()
    file_id = extract_drive_id(audio_url)

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = os.path.join(tmpdir, f"{case_id}.mp3")
        download_from_drive(drive_service, file_id, mp3_path)

        wav_path = process_mp3_to_wav16k(mp3_path, WAV_OUTPUT_DIR)
        gcs_uri = upload_temp_to_gcs(wav_path, TEMP_BUCKET)

        chunks = split_wav_chunks(wav_path)
        transcript_parts = [transcribe_audio_chunk(chunk) for chunk in chunks]

        delete_gcs_blob(TEMP_BUCKET, os.path.basename(wav_path))
        return "\n".join(transcript_parts)
