# tests/test_audio_normalizer_service.py
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.settings import GCS_BUCKET

if __name__ == "__main__":
    mp3_uri = "gs://my-bucket-out/12_Alex Hernández.mp3"  # el que subiste antes
    case_id = "12_Alex_Hernandez"
    wav_uri = normalize_and_upload_gcs(mp3_uri, case_id, GCS_BUCKET)
    print("✅ WAV disponible en:", wav_uri)
