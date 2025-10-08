# tests/test_gemini.py
from pathlib import Path
from src.transcription.gemini_transcriber import transcribe_audio_chunk

if __name__ == "__main__":
    wav_file = Path("./data/wav16k/audio_prueba.wav")
    text = transcribe_audio_chunk(wav_file)
    print("Texto transcrito:\n", text)
