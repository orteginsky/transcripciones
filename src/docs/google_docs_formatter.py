# src/docs/google_docs_formatter.py (versión corregida)
#librerias locales
import re
from datetime import datetime
from typing import List, Dict, Any

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def generate_google_docs_requests(title: str, transcript_text: str) -> List[Dict[str, Any]]:
    """
    Formatea una transcripción y genera una lista de requests para la API de Google Docs,
    ajustando dinámicamente los índices de inserción y estilo.

    Args:
        title (str): El título del documento.
        transcript_text (str): El texto de la transcripción.

    Returns:
        List[Dict[str, Any]]: Una lista de requests para el método batchUpdate de la API.
    """
    requests = []
    current_index = 1 # El índice 1 es el inicio del cuerpo del documento.

    # 1. Título del Documento
    requests.append({
        "insertText": {
            "location": {"index": current_index},
            "text": title
        }
    })
    requests.append({
        "updateParagraphStyle": {
            "range": {"startIndex": current_index, "endIndex": current_index + len(title)},
            "paragraphStyle": {"alignment": "CENTER"},
            "fields": "alignment"
        }
    })
    current_index += len(title)

    # 2. Fecha de Procesamiento
    date_str = f"\nProcesado el {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    requests.append({
        "insertText": {
            "location": {"index": current_index},
            "text": date_str
        }
    })
    current_index += len(date_str)

    # 3. Contenido de la Transcripción
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        text_to_insert = line + "\n"
        
        # Insertar el texto de la línea
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": text_to_insert
            }
        })

        # Aplicar estilo al texto recién insertado
        text_length = len(text_to_insert)
        style_request = {
            "updateTextStyle": {
                "range": {
                    "startIndex": current_index,
                    "endIndex": current_index + text_length
                },
                "textStyle": {},
                "fields": "foregroundColor" # Por defecto, solo el color de texto
            }
        }
        
        timestamp_match = re.search(r"\[\d{1,2}:\d{2}:\d{2}\]", line)
        speaker_match = re.match(r"([A-Za-zÁÉÍÓÚáéíóúüÜñÑ\s]+):\s*(.*)", line)
        is_note = line.startswith("[Nota:") or line.startswith("[Observación")
        
        if timestamp_match and speaker_match:
            # Estilo para el diálogo (negrita y color)
            style_request["updateTextStyle"]["textStyle"]["bold"] = True
            style_request["updateTextStyle"]["textStyle"]["foregroundColor"] = {"color": {"rgbColor": {"red": 0.0, "green": 0.2, "blue": 0.6}}}
            style_request["updateTextStyle"]["fields"] += ",bold"
        elif is_note:
            # Estilo para las notas (cursiva y color gris)
            style_request["updateTextStyle"]["textStyle"]["italic"] = True
            style_request["updateTextStyle"]["textStyle"]["foregroundColor"] = {"color": {"rgbColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}
            style_request["updateTextStyle"]["fields"] += ",italic"
        
        requests.append(style_request)
        
        # Incrementar el índice para la siguiente inserción
        current_index += text_length
        
    logger.info("Requests de formato generados exitosamente. Total de requests: %d", len(requests))
    return requests