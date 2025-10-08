from src.logging_conf import setup_logging
from src.ingestion.audio_processor import process_mp3_to_wav16k
from src.storage.gcs_uploader import upload_to_gcs
from src.transcription.stt_batch import transcribe_from_gcs
from src.settings import WAV_OUTPUT_DIR, NORMALIZE_TARGET_DB


from pathlib import Path

def main():
    setup_logging("INFO")

    # 1. Normalizar
    mp3 = Path("./data/input/audio_prueba.mp3")
    wav_path = process_mp3_to_wav16k(mp3, WAV_OUTPUT_DIR, target_dbfs=NORMALIZE_TARGET_DB)

    # 2. Subir a GCS
    gcs_uri = upload_to_gcs(wav_path)

    # 3. Transcribir
    text = transcribe_from_gcs(gcs_uri)
    print("Transcripción:\n", text)

if __name__ == "__main__":
    main()
