# src/orchestration/runner.py
from src.ingestion.auth_service import get_google_creds_service
from src.ingestion.sheet_loader import get_audio_links
from src.ingestion.drive_loader import download_from_drive, extract_drive_id
from src.ingestion.audio_processor import process_mp3_to_wav16k, split_wav_chunks
from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.settings import INPUT_DIR, WAV_OUTPUT_DIR
from src.logging_conf import get_logger

logger = get_logger(__name__)

def run_pipeline1(sheet_id: str, range_: str):
    sheets_service, drive_service, _ = get_google_creds_service()

    rows = get_audio_links(sheets_service, sheet_id, range_)
    for row in rows:
        audio_link = str(row.get("link"))
        file_id = extract_drive_id(audio_link)

        if not file_id:
            logger.warning("No se pudo extraer file_id de %s", audio_link)
            continue

        mp3_path = INPUT_DIR / f"{file_id}.mp3"
        logger.info("Descargando archivo %s a %s", file_id, mp3_path)
        download_from_drive(drive_service, file_id, mp3_path)

        logger.info("Procesando %s → WAV 16k", mp3_path)
        wav_file = process_mp3_to_wav16k(mp3_path, WAV_OUTPUT_DIR)
        chunks = split_wav_chunks(wav_file)

        transcript = []
        for chunk in chunks:
            logger.info("Transcribiendo chunk: %s", chunk)
            transcript.append(transcribe_audio_chunk(chunk))

        full_transcript = "\n".join(transcript)
        print("TRANSCRIPCIÓN FINAL:\n", full_transcript)
        return full_transcript  # 👈 opcional, útil para test



def run_pipeline2(sheet_id: str, range_: str):
    sheets_service, drive_service, _ = get_google_creds_service()

    rows = get_audio_links(sheets_service, sheet_id, range_)
    transcripts = []

    for row in rows:
        audio_link = str(row.get("link"))
        file_id = extract_drive_id(audio_link)

        mp3_path = INPUT_DIR / f"{file_id}.mp3"
        download_from_drive(drive_service, file_id, mp3_path)

        wav_file = process_mp3_to_wav16k(mp3_path, WAV_OUTPUT_DIR)
        chunks = split_wav_chunks(wav_file)

        transcript_chunks = []
        for chunk in chunks:
            transcript_chunks.append(transcribe_audio_chunk(chunk))

        transcript = "\n".join(transcript_chunks)
        transcripts.append(transcript)

    # Devuelve el resultado completo
    return "\n\n".join(transcripts)

if __name__ == "__main__":
    #necesito un ID de la sheet
    #necesito un Range
    range = "local!A1:F100"
    sheet_id = "1Dyq4QJgwKcW3LEAetga43CkAdvzBZDtW7vLddPugVfo"
    run_pipeline1(sheet_id, range)