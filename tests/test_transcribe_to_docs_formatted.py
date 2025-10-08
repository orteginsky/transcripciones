# tests/test_transcribe_to_docs_formatted.py
from pathlib import Path
from src.transcription.gemini_transcriber import transcribe_audio_chunk
from src.docs.google_docs_formatter import create_formatted_google_doc

if __name__ == "__main__":
    wav_file = Path("./data/wav16k/audio_prueba.wav")

    print("🎙️ Transcribiendo audio con Gemini...")
    text = transcribe_audio_chunk(wav_file)

    if not text:
        print("❌ No se obtuvo texto.")
    else:
        print("✅ Transcripción completa, creando documento con formato...")
        link = create_formatted_google_doc(
            title="Transcripción formateada - Prueba local",
            transcript_text=text
        )
        print("📄 Documento creado y compartido:\n", link)
