# src/transcription/gemini_vertex_transcriber.py
from vertexai.generative_models import GenerativeModel, Part
import vertexai
from src.settings import get_settings
from src.logging_conf import get_logger

logger = get_logger(__name__)


def gemini_vertex_transcribe_gcs(
    gcs_uri: str,
    *,
    model_name: str = "gemini-2.5-flash",
    mime_type: str = "audio/wav",
    prompt: str | None = None,
) -> str:
    """
    Transcribe un archivo de audio en GCS usando Vertex AI Gemini 2.5 Flash Preview.
    - Acepta URIs gs://
    - Usa el prompt proporcionado o el definido en settings (TRANSCRIPTION_PROMPT_TEMPLATE).
    - Incluye logs detallados para diagnóstico.
    """

    # --- Configuración base ---
    s = get_settings()
    vertexai.init(project=s.gcp_project_id, location="us-central1")

    logger.info("🎧 Iniciando transcripción con Vertex Gemini (%s) para %s", model_name, gcs_uri)

    # --- Determinar el prompt ---
    prompt_text = (
        prompt
        or getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
        or (
            "Transcribe fielmente el audio en español (sin parafrasear). "
            "Usa puntuación básica y marca lo inaudible como [Nota: inaudible]."
        )
    )

    # Refuerzo de formato
    prompt_text += (
        "\n\n⚠️ IMPORTANTE: "
        """
        Transcribe el siguiente audio siguiendo **estrictamente** el formato indicado.

        ## FORMATO DE SALIDA REQUERIDO:
        - Usa marcas de tiempo en formato `[HH:MM:SS]` o `[MM:SS]` (elige el que corresponda según la duración).
        - Identifica a cada hablante con un nombre simple, por ejemplo: **Entrevistador, Testigo, Speaker 1, Speaker 2**.
        - Cada línea debe tener el siguiente formato:
        [MARCA_DE_TIEMPO] HABLADOR: Diálogo
        - Incluye notas contextuales entre corchetes. Ejemplos:
        - `[Nota: El cliente se nota que está llorando]`
        - `[Nota: El audio es inaudible]`
        - `[Nota: No se entiende]`
        - No combines múltiples intervenciones en una sola línea.  
        Cada cambio de hablante o cada nota debe ir en una nueva línea.

        ## EJEMPLO DEL FORMATO ESPERADO:

        [00:05] Entrevistador: ¿Puede contarme sobre el incidente?
        [00:15] Testigo: Sí, lo vi todo. El abusador gritaba mucho. [Nota: El testigo se nota nervioso]
        [00:25] Entrevistador: ¿Y qué pasó después?
        [00:30] Testigo: Él se fue. Después, el cliente se puso a llorar.
        [00:45] [Nota: Se escucha un ruido de fondo que interrumpe]
        """
    )

    # --- Logs de diagnóstico ---
    logger.info("🧠 Prompt aplicado (%d chars): %.200s...", len(prompt_text), prompt_text.replace("\n", " ")[:200])

    # --- Construcción del input ---
    audio_part = Part.from_uri(gcs_uri, mime_type=mime_type)

    # --- Ejecución del modelo ---
    model = GenerativeModel(model_name)
    try:
        response = model.generate_content([prompt_text, audio_part])
    except Exception as e:
        logger.error("❌ Error al llamar a Gemini Vertex: %s", e)
        raise

    # --- Procesamiento del resultado ---
    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("❌ Respuesta vacía desde Vertex Gemini (sin texto).")

    logger.info("✅ Transcripción completada (%d caracteres)", len(text))
    return text
