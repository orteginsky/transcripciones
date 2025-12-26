import os
from google import genai
from google.genai import types

from src.settings import settings
from src.logging_conf import get_logger

logger = get_logger(__name__)

def transcribe_with_gemini(
    gcs_uri: str,
    model_name: str = settings.gemini_vertex,
    mime_type: str = "audio/mpeg"
) -> str:
    """
    Envía audio/video a Vertex AI usando el SDK unificado (Gen AI) v1.
    """
    try:
        logger.info(f"🤖 Inicializando cliente GenAI para modelo: {model_name}")
        
        # --- CAMBIO IMPORTANTE BASADO EN TU DOCUMENTACIÓN ---
        # 1. Vertex AI requiere habilitar 'vertexai=True'.
        # 2. Para modelos PREVIEW (como Gemini 3), es CRUCIAL usar 'v1beta1'.
        # 3. location='us-central1' es donde tu script encontró el modelo.
        
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region, # Debería ser 'us-central1' según tu .env
            http_options={'api_version': 'v1beta1'}  # <--- ESTA ES LA CLAVE PARA EL ERROR 404
        )

        # Preparar el archivo (Audio)
        media_part = types.Part.from_uri(
            file_uri=gcs_uri,
            mime_type=mime_type
        )

        # Preparar el Prompt
        prompt_text = """
Actúa como un transcriptor profesional experto. Transcribe el siguiente archivo de audio/video de forma LITERAL (verbatim).

Instrucciones críticas:
1. Identifica a los hablantes (Ej: Agente, Cliente, Hablante 1, Hablante 2)
2. INCLUYE MARCAS DE TIEMPO al inicio de cada turno: [MM:SS]
3. Transcribe TODO literalmente: repeticiones, muletillas, pausas.
4. Formato ESTRICTO por línea:
   [MM:SS] Hablante X: Texto completo...
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

        if not response or not response.text:
            raise ValueError("Gemini devolvió una respuesta vacía")

        logger.info(f"✅ Transcripción recibida ({len(response.text)} chars)")
        return response.text

    except Exception as e:
        logger.error(f"❌ Error en Vertex AI ({model_name}): {e}")
        # Intentamos mostrar más detalles si el error viene de la API
        if hasattr(e, 'message'):
             logger.error(f"Detalle API: {e.message}")
        raise e