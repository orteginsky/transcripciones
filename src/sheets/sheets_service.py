from typing import Dict, Any
from src.ingestion.auth_service import get_google_creds_service
from src.logging_conf import get_logger

logger = get_logger(__name__)

def update_row_status(
    spreadsheet_id: str,
    sheet_name: str,
    row_index: int,
    col_letter: str,
    value: str
):
    """
    Escribe un valor en una celda específica.
    Args:
        spreadsheet_id: ID de la hoja de cálculo
        sheet_name: Nombre de la pestaña
        row_index: Índice 1-based (tal cual sale en la UI de Sheets)
        col_letter: 'A', 'B', 'Z', etc.
        value: Valor a escribir
    """
    _, _, sheets_service, _ = get_google_creds_service()
    # En src/sheets/sheets_service.py
    # Asegúrate de que tenga las comillas simples (') rodeando {sheet_name}
    range_name = f"'{sheet_name}'!{col_letter}{row_index}"
    body = {"values": [[value]]}
    try:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        logger.info(f"📊 Sheet actualizada: {range_name} -> {value}")
    except Exception as e:
        logger.error(f"❌ Error escribiendo en Sheet {spreadsheet_id}: {e}")
        # No relanzamos el error para no fallar todo el pipeline si solo falla el reporte


def update_transcription_result(
    spreadsheet_id: str,
    sheet_name: str,
    row_index: int,
    result: Dict[str, Any]
):
    """
    Actualiza múltiples columnas con el resultado de la transcripción.
    Args:
        spreadsheet_id: ID de la hoja de cálculo
        sheet_name: Nombre de la pestaña
        row_index: Fila a actualizar (1-based)
        result: Dict con los datos del resultado:
            - doc_url: URL del documento de Google Docs
            - status: Estado (ej. "✅ Transcrito" o "❌ Error")
            - engine: Motor usado ("STT V1" o "Gemini 2.5 Flash")
            - duration_seconds: Duración del proceso en segundos
            - transcript_doc_col: Columna para doc_url (opcional)
            - status_col: Columna para status (opcional)
            - engine_col: Columna para engine (opcional)
            - duration_col: Columna para duration (opcional)
    """
    _, _, sheets_service, _ = get_google_creds_service()

    updates = []

    # Preparar los datos a actualizar
    if result.get("transcript_doc_col") and result.get("doc_url"):
        updates.append({
            "range": f"'{sheet_name}'!{result['transcript_doc_col']}{row_index}", # <--- AQUÍ
            "values": [[result["doc_url"]]]
        })

    if result.get("status_col") and result.get("status"):
        updates.append({
            "range": f"'{sheet_name}'!{result['status_col']}{row_index}", # <--- AQUÍ
            "values": [[result["status"]]]
        })

    if result.get("engine_col") and result.get("engine"):
        updates.append({
            "range": f"'{sheet_name}'!{result['engine_col']}{row_index}", # <--- AQUÍ
            "values": [[result["engine"]]]
        })

    if result.get("duration_col") and result.get("duration_seconds"):
        duration = result["duration_seconds"]
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        formatted_duration = f"{minutes:02d}:{seconds:02d}"
        updates.append({
            "range": f"'{sheet_name}'!{result['duration_col']}{row_index}", # <--- AQUÍ
            "values": [[formatted_duration]]
        })
    if not updates:
        logger.warning("⚠️ No hay columnas configuradas para actualizar en Sheets")
        return

    try:
        # Batch update para eficiencia
        body = {"data": updates, "valueInputOption": "USER_ENTERED"}
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        logger.info(f"📊 Sheet actualizada con {len(updates)} campos en fila {row_index}")
    except Exception as e:
        logger.error(f"❌ Error actualizando Sheet {spreadsheet_id}: {e}")
        # No relanzamos el error para no fallar todo el pipeline