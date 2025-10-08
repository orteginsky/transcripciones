# src/ingestion/sheet_loader.py
from typing import List, Dict
from src.logging_conf import get_logger

logger = get_logger(__name__)

def get_audio_links(sheets_service, spreadsheet_id: str, range_: str, link_col: int = 5) -> List[Dict]:
    """
    Lee una hoja de cálculo de Google Sheets y extrae enlaces de audio.

    Args:
        sheets_service: Objeto servicio de Sheets API (ya autenticado).
        spreadsheet_id (str): ID de la hoja de cálculo.
        range_ (str): Rango de celdas a leer (ej: "Hoja1!A2:F100").
        link_col (int): Índice de columna con links de audio (0-based).

    Returns:
        List[Dict]: lista de dicts con información de la fila, ej:
            [
              {"row": 2, "link": "https://drive.google.com/file/d/..."},
              {"row": 3, "link": "..."}
            ]
    """
    try:
        result = (
            sheets_service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_)
            .execute()
        )
        values = result.get("values", [])

        if not values:
            logger.warning("No se encontraron valores en la hoja %s (%s)", spreadsheet_id, range_)
            return []

        audio_rows = []
        for idx, row in enumerate(values, start=2):  # empezamos en fila 2 (salta encabezado)
            link = row[link_col].strip() if len(row) > link_col and row[link_col] else ""
            if link:
                audio_rows.append({"row": idx, "link": link})
                logger.debug("Fila %d: link extraído = %s", idx, link)

        logger.info("Se encontraron %d enlaces de audio en la hoja.", len(audio_rows))
        return audio_rows

    except Exception as e:
        logger.exception("Error al leer la hoja de cálculo %s: %s", spreadsheet_id, e)
        return []
