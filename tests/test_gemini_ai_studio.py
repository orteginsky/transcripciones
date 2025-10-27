from src.transcription.transcribers import gemini_transcribe_gcs

print(gemini_transcribe_gcs("gs://my-bucket-out/processed/prueba_16k.wav"))
