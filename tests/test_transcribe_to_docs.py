# tests/test_transcribe_to_docs.py
from pathlib import Path
from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.docs.google_docs_writer import create_google_doc_from_transcript

if __name__ == "__main__":
    wav_file = Path("./data/wav16k/audio_prueba.wav")

    print("🎙️  Transcribiendo audio con Gemini...")
    text = transcribe_audio_chunk(wav_file)

    if not text:
        print("❌ No se obtuvo texto de transcripción.")
    else:
        print("✅ Transcripción completa, creando documento...")

        public_link = create_google_doc_from_transcript(
            title="Transcripción de prueba - Alex Hernández",
            transcript_text=text
        )

        print(f"📄 Documento creado: {public_link}")
