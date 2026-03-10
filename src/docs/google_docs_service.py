from __future__ import annotations
from typing import Dict, Any, List
from googleapiclient.errors import HttpError
from src.ingestion.auth_service import get_google_creds_service
from src.logging_conf import get_logger

logger = get_logger(__name__)

def _get_doc_end_index(docs_service, doc_id: str) -> int:
    """Obtiene el índice del final del documento."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])
    if not content:
        return 1
    return content[-1]["endIndex"] - 1

def _create_compact_requests(transcript_text: str, start_index: int, title: str) -> List[Dict[str, Any]]:
    """
    Genera peticiones para formato COMPACTO (Arial 11):
    [00:00] Agente: Texto de la conversación...
    """
    requests = []
    current_index = start_index

    # 1. Insertar Header
    header_text = f"\n--- 🎙️ TRANSCRIPCIÓN: {title} ---\n\n"
    requests.append({
        'insertText': {
            'location': {'index': current_index},
            'text': header_text
        }
    })
    
    # Estilo del Header (Gris, Negrita, 11pt)
    requests.append({
        'updateTextStyle': {
            'range': {
                'startIndex': current_index + 1, 
                'endIndex': current_index + len(header_text) - 1
            },
            'textStyle': {
                'bold': True,
                'fontSize': {'magnitude': 11, 'unit': 'PT'},
                'foregroundColor': {'color': {'rgbColor': {'red': 0.3, 'green': 0.3, 'blue': 0.3}}}
            },
            'fields': 'bold,fontSize,foregroundColor'
        }
    })
    current_index += len(header_text)

    # 2. Procesar bloques
    blocks = transcript_text.split('\n\n')

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        if "|SEPARATOR|" in block:
            parts = block.split("|SEPARATOR|")
            prefix_part = parts[0].strip() # Ej: "[00:00] Agente:"
            content_part = parts[1].strip() # Ej: "Hola..."
            
            # --- CAMBIO CLAVE: Misma línea ---
            # Agregamos un espacio después de los dos puntos
            full_line = f"{prefix_part} {content_part}\n"
            
            # A) Insertar línea completa
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': full_line
                }
            })

            # B) Formatear PREFIJO (Negrita, Arial 11)
            prefix_end = current_index + len(prefix_part)
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': prefix_end
                    },
                    'textStyle': {
                        'bold': True,
                        'weightedFontFamily': {'fontFamily': 'Arial'},
                        'fontSize': {'magnitude': 11, 'unit': 'PT'},
                        'foregroundColor': {'color': {'rgbColor': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}}
                    },
                    'fields': 'bold,weightedFontFamily,fontSize,foregroundColor'
                }
            })

            # C) Formatear CONTENIDO (Normal, Arial 11)
            line_end = current_index + len(full_line)
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': prefix_end, # Desde donde termina el prefijo
                        'endIndex': line_end
                    },
                    'textStyle': {
                        'bold': False,
                        'weightedFontFamily': {'fontFamily': 'Arial'},
                        'fontSize': {'magnitude': 11, 'unit': 'PT'},
                        'foregroundColor': {'color': {'rgbColor': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}}
                    },
                    'fields': 'bold,weightedFontFamily,fontSize,foregroundColor'
                }
            })

            # D) Ajustar Párrafo (Espaciado compacto 1.15)
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': line_end
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'NORMAL_TEXT',
                        'spaceAbove': {'magnitude': 0, 'unit': 'PT'},
                        'spaceBelow': {'magnitude': 4, 'unit': 'PT'}, # Pequeña separación entre diálogos
                        'lineSpacing': 115 # 1.15 líneas
                    },
                    'fields': 'namedStyleType,spaceAbove,spaceBelow,lineSpacing'
                }
            })

            current_index += len(full_line)
        
        else:
            # Fallback para texto sin formato
            fallback_text = f"{block}\n"
            requests.append({
                'insertText': {'location': {'index': current_index}, 'text': fallback_text}
            })
            current_index += len(fallback_text)

    return requests

def append_formatted_transcript(doc_id: str, title: str, transcript_text: str) -> dict:
    _, docs_service, _, _ = get_google_creds_service()
    try:
        end_index = _get_doc_end_index(docs_service, doc_id)
        requests = _create_compact_requests(transcript_text, end_index, title) # Usamos la nueva función

        if not requests:
            logger.warning(f"No hay contenido para insertar en el doc {doc_id}")
            return {}

        result = docs_service.documents().batchUpdate(
            documentId=doc_id, 
            body={'requests': requests}
        ).execute()
        
        logger.info(f"✅ Transcripción insertada (Arial 11 Compacto) en Doc: {doc_id}")
        return result

    except HttpError as e:
        logger.error(f"❌ Error en Google Docs API: {e}")
        raise RuntimeError(f"Docs API error: {e}") from e

