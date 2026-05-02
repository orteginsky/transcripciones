import json
from google import genai
from google.genai import types

from src.settings import settings
from src.logging_conf import get_logger
from src.ingestion.auth_service import get_oauth2_credentials

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt de transcripción forense por fragmento
# Optimizado para que Gemini Flash devuelva JSON puro con marcas de tiempo.
# ---------------------------------------------------------------------------
TRANSCRIPTION_PROMPT_TEMPLATE = """\
Actúa como un motor de transcripción forense. Tu salida DEBE ser únicamente un JSON válido.

DATOS DEL FRAGMENTO:
- ID de Parte: {fragment_id}
- Calidad de origen: 8kHz (Low Fidelity)
- Instrucción: Identifica hablantes como SPEAKER_1_{fragment_id} y SPEAKER_2_{fragment_id}.

REGLAS ESTRICTAS:
1. No inventes marcas de tiempo más allá de la duración real del archivo.
2. Si el audio es ininteligible, usa [inaudible].
3. NO incluyas ningún texto fuera del JSON (sin markdown, sin explicaciones).
4. Formato de salida: JSON puro.

ESTRUCTURA REQUERIDA:
{{
  "part": "{fragment_id}",
  "data": [
    {{
      "start": "MM:SS",
      "spk": "SPEAKER_N_{fragment_id}",
      "text": "..."
    }}
  ]
}}
"""


def _extract_text(response) -> str:
    """
    Extrae el texto de una respuesta GenAI de forma robusta.

    gemini-3-flash-preview (modelo con thinking) puede devolver `response.text = None`
    porque los thought-parts tienen role distinto al texto final. Iteramos los parts
    del primer candidato y concatenamos solo los que contienen texto plano.
    """
    # Caso simple: el SDK ya consolidó el texto
    if response.text:
        return response.text

    # Fallback: iterar partes del primer candidato
    try:
        parts = response.candidates[0].content.parts
        return "".join(
            p.text for p in parts if hasattr(p, "text") and p.text
        )
    except (IndexError, AttributeError, TypeError):
        return ""


def transcribe_with_gemini(
    gcs_uri: str,
    model_name: str = settings.gemini_vertex,
    mime_type: str = "audio/mpeg",
    language_code: str = "es-MX"
) -> str:
    """
    Envía audio/video a Vertex AI usando el SDK unificado (Gen AI) v1.
    Usa credenciales OAuth2 (token.json) para autenticarse contra el endpoint global.
    """
    try:
        logger.info(f"🤖 Inicializando cliente GenAI para modelo: {model_name}")

        # Credenciales OAuth2 (token.json) — requerido para el endpoint global de Gemini 3.
        creds = get_oauth2_credentials()

        # location='global' es obligatorio para modelos Gemini 3 preview.
        # api_version='v1' — confirmado funcional via curl; v1beta1 no es necesario.
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,   # default: "global" (settings.py)
            credentials=creds,
            http_options={"api_version": "v1"},
        )

        # Preparar el archivo (Audio)
        media_part = types.Part.from_uri(
            file_uri=gcs_uri,
            mime_type=mime_type
        )

        # Preparar el Prompt
        prompt_text = f"""
Actúa como un transcriptor profesional experto. Transcribe el siguiente archivo de audio/video de forma LITERAL (verbatim).

Instrucciones críticas:
1. Identifica a los hablantes (Ej: Agente, Cliente, Hablante 1, Hablante 2)
2. INCLUYE MARCAS DE TIEMPO al inicio de cada turno: [MM:SS]
3. Transcribe TODO literalmente: repeticiones, muletillas, pausas.
4. Formato ESTRICTO por línea:
   [MM:SS] Hablante X: Texto completo...
5. El idioma del audio es: {language_code}. La transcripción DEBE estar en ese idioma.
"""
        
        # Configuración del modelo (Gemini 3 soporta configuraciones avanzadas)
        generate_config = types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            max_output_tokens=8192,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_ONLY_HIGH"
                ),
            ]
        )

        logger.info(f"📤 Enviando archivo a Gemini ({model_name})...")

        # Llamada de generación
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[media_part, types.Part.from_text(text=prompt_text)]
                )
            ],
            config=generate_config
        )

        # gemini-3-flash-preview es un modelo con "thinking": response.text puede ser None
        # aunque la llamada sea exitosa. Extraemos texto de los parts directamente.
        text = _extract_text(response)
        if not text:
            raise ValueError("Gemini devolvió una respuesta vacía")

        logger.info(f"✅ Transcripción recibida ({len(text)} chars)")
        return text

    except Exception as e:
        logger.error(f"❌ Error en Vertex AI ({model_name}): {e}")
        # Intentamos mostrar más detalles si el error viene de la API
        if hasattr(e, 'message'):
             logger.error(f"Detalle API: {e.message}")
        raise e


# ---------------------------------------------------------------------------
# Transcripción por fragmento (pipeline de segmentación)
# ---------------------------------------------------------------------------

def transcribe_fragment_with_gemini(
    gcs_uri: str,
    fragment_id: str,
    model_name: str = settings.gemini_vertex,
    mime_type: str = "audio/mpeg",
) -> dict:
    """
    Transcribe un fragmento de audio usando TRANSCRIPTION_PROMPT_TEMPLATE.

    Inyecta el `fragment_id` en el prompt para que Gemini etiquete a los
    hablantes como SPEAKER_1_<fragment_id>, SPEAKER_2_<fragment_id>, etc.
    y devuelva un JSON estructurado con marcas de tiempo por turno.

    Args:
        gcs_uri:      URI del fragmento en GCS (gs://bucket/path).
        fragment_id:  Identificador del fragmento, p.ej. "P01", "P02"...
        model_name:   Modelo Gemini a usar (default: settings.gemini_vertex).
        mime_type:    MIME type del fragmento de audio.

    Returns:
        dict con la estructura:
            {
                "part": "<fragment_id>",
                "data": [
                    {"start": "MM:SS", "spk": "SPEAKER_N_<fragment_id>", "text": "..."},
                    ...
                ]
            }

    Raises:
        ValueError: Si Gemini devuelve una respuesta vacía o JSON inválido.
    """
    try:
        logger.info(f"🤖 [{fragment_id}] Inicializando cliente GenAI: {model_name}")

        creds = get_oauth2_credentials()
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
            credentials=creds,
            http_options={"api_version": "v1"},
        )

        media_part = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)
        prompt_text = TRANSCRIPTION_PROMPT_TEMPLATE.format(fragment_id=fragment_id)

        generate_config = types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            max_output_tokens=8192,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_ONLY_HIGH"
                ),
            ]
        )

        logger.info(f"📤 [{fragment_id}] Enviando fragmento a Gemini (mime: {mime_type})...")

        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[media_part, types.Part.from_text(text=prompt_text)]
                )
            ],
            config=generate_config
        )

        raw_text = _extract_text(response)
        if not raw_text:
            raise ValueError(f"[{fragment_id}] Gemini devolvió una respuesta vacía")

        # Limpiar posibles bloques markdown ```json ... ``` que el modelo añada
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = "\n".join(clean.split("\n")[:-1])
        clean = clean.strip()

        try:
            result = json.loads(clean)
        except json.JSONDecodeError as je:
            logger.warning(
                f"⚠️ [{fragment_id}] JSON inválido de Gemini, devolviendo estructura vacía. Error: {je}"
            )
            result = {"part": fragment_id, "data": [], "raw": raw_text}

        logger.info(
            f"✅ [{fragment_id}] Fragmento transcrito "
            f"({len(result.get('data', []))} turnos)"
        )
        return result

    except Exception as e:
        logger.error(f"❌ [{fragment_id}] Error en Vertex AI: {e}")
        if hasattr(e, 'message'):
            logger.error(f"   Detalle API: {e.message}")
        raise