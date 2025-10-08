# src/docs/google_docs_formatter.py
import re
from datetime import datetime
from googleapiclient.discovery import build
from src.ingestion.google_auth_manager import get_google_services
from src.logging_conf import get_logger

logger = get_logger(__name__)

def create_formatted_google_doc(title: str, transcript_text: str) -> str:
    """
    Crea un documento de Google Docs formateado con:
      - Título centrado
      - Fecha de procesamiento
      - Líneas de diálogo estilizadas (hablante / notas)
    Devuelve la URL pública editable del documento.
    """
    _, _, creds = get_google_services()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # 1️⃣ Crear el documento base
    doc = docs_service.documents().create(body={"title": title}).execute()
    doc_id = doc.get("documentId")
    logger.info(f"Documento creado: {doc_id}")

    # 2️⃣ Preparar contenido inicial
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = transcript_text.splitlines()
    requests = []

    # Encabezado del documento
    requests.extend([
        {"insertText": {"location": {"index": 1}, "text": f"{title}\n"}},
        {"updateParagraphStyle": {
            "range": {"startIndex": 1, "endIndex": len(title) + 1},
            "paragraphStyle": {"alignment": "CENTER"},
            "fields": "alignment"
        }},
        {"insertText": {"location": {"index": len(title) + 1}, "text": f"Procesado el {date_str}\n\n"}}
    ])

    current_index = len(title) + len(date_str) + 5

    # 3️⃣ Analizar cada línea y aplicar formato
    for line in lines:
        if not line.strip():
            continue

        timestamp_match = re.search(r"\[(\d{1,2}:\d{2}:\d{2})\]", line)
        speaker_match = re.match(r"([A-Za-zÁÉÍÓÚáéíóúüÜñÑ\s]+):\s*(.*)", line)
        is_note = line.strip().startswith("[Nota:") or line.strip().startswith("[Observación")

        line_text = line.strip() + "\n"
        line_length = len(line_text)

        # Insertar texto
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": line_text
            }
        })

        # Aplicar estilo según tipo de línea
        if timestamp_match and speaker_match:
            # Ejemplo: [00:00:10] Entrevistador: Buenos días
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": current_index + len(line_text)
                    },
                    "textStyle": {
                        "bold": True,
                        "foregroundColor": {"color": {"rgbColor": {"red": 0.0, "green": 0.2, "blue": 0.6}}}
                    },
                    "fields": "bold,foregroundColor"
                }
            })
        elif is_note:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": current_index + len(line_text)
                    },
                    "textStyle": {
                        "italic": True,
                        "foregroundColor": {"color": {"rgbColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}
                    },
                    "fields": "italic,foregroundColor"
                }
            })
        else:
            # Texto normal
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": current_index + len(line_text)
                    },
                    "textStyle": {
                        "foregroundColor": {"color": {"rgbColor": {"red": 0, "green": 0, "blue": 0}}}
                    },
                    "fields": "foregroundColor"
                }
            })

        current_index += line_length

    # 4️⃣ Enviar las actualizaciones en lote
    logger.info("Aplicando formato y escribiendo contenido...")
    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    # 5️⃣ Configurar permisos (editable para cualquiera con el enlace)
    permission = {"type": "anyone", "role": "writer"}
    drive_service.permissions().create(fileId=doc_id, body=permission).execute()

    public_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    logger.info(f"Documento final disponible en: {public_url}")
    return public_url
    