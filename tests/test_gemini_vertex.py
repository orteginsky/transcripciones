from src.transcription.transcribers import gemini_vertex_transcribe_gcs
print(gemini_vertex_transcribe_gcs("gs://my-bucket-out/processed/prueba_16k.wav"))
