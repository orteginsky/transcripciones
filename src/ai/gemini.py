# src/ai/gemini.py
# Librerias externas
import google.generativeai as genai

# Módulos Globales
from src.logging_conf import get_logger
from src.settings import GEMINI_API_KEY

logger = get_logger(__name__)

def configure_gemini():
    """Configura la librería de Gemini con la API Key."""
    if not GEMINI_API_KEY:
        raise ValueError("Falta la variable GEMINI_API_KEY en settings/env")
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configurada correctamente.")


def load_model(model_name: str, fallback: str, generation_config: dict = None):
    """
    Intenta cargar un modelo de Gemini, si falla usa un modelo de respaldo.
    """
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config or {"temperature": 0.2}
        )
        logger.info("Modelo %s cargado exitosamente.", model_name)
        return model
    except Exception as e:
        logger.error("No se pudo cargar %s: %s. Reintentando con %s...",
                     model_name, e, fallback)
        model = genai.GenerativeModel(
            model_name=fallback,
            generation_config=generation_config or {"temperature": 0.2}
        )
        logger.info("Modelo %s cargado como fallback.", fallback)
        return model
