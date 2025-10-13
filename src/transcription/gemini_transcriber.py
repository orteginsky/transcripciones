# src/transcription/gemini_transcriber.py
# Librerias externas
import google.generativeai as genai

# Librerias internas
from pathlib import Path

# Módulos
from src.ai.gemini import configure_gemini, load_model

# Módulos Globales
from src.logging_conf import get_logger
from src.settings import TRANSCRIPTION_PROMPT_TEMPLATE

logger = get_logger(__name__)

# Carga inicial del modelo
configure_gemini()
llm_transcription_model = load_model(
    model_name="gemini-2.5-flash",
    fallback="gemini-pro",
    generation_config={"temperature": 0.0}
)

def transcribe_audio_chunk(audio_chunk_path: Path) -> str:
    """
    Envía un fragmento de audio a Gemini para obtener transcripción.
    """
    logger.info("Subiendo fragmento de audio a Gemini: %s", audio_chunk_path)

    try:
        # 1. Subir audio a Gemini (✅ se usa genai.upload_file, no model.upload_file)
        audio_part = genai.upload_file(path=str(audio_chunk_path))

        # 2. Construir el prompt
        contents = [TRANSCRIPTION_PROMPT_TEMPLATE, audio_part]

        # 3. Generar transcripción
        response = llm_transcription_model.generate_content(contents)
        transcript = response.text.strip()

        logger.info("Transcripción completada para %s", audio_chunk_path)
        return transcript

    except Exception as e:
        logger.exception("Error al transcribir fragmento %s: %s", audio_chunk_path, e)
        return ""
