# src/ingestion/drive_loader.py
# Librerias externas
from googleapiclient.http import MediaIoBaseDownload
from pydantic import HttpUrl

# Librerias internas
import io
import re
from pathlib import Path

# Módulo Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)


def extract_drive_id(audio_link: str) -> str:
    """
    Extrae el file_id de un enlace de Google Drive.
    Soporta patrones como:
      - https://drive.google.com/file/d/FILE_ID/view
      - https://drive.google.com/open?id=FILE_ID
    """
    if not audio_link:
        logger.warning("El enlace de audio está vacío o None")
        return ""

    match = re.search(r'(?:id=([a-zA-Z0-9_-]+)|file/d/([a-zA-Z0-9_-]+))', audio_link)
    file_id = match.group(1) or match.group(2) if match else None

    if file_id:
        logger.debug("Extraído file_id='%s' desde enlace='%s'", file_id, audio_link)
    else:
        logger.error("No se pudo extraer file_id del enlace: %s", audio_link)
        return ""

    return file_id


def download_from_drive(drive_service, file_id: str, dest: Path) -> Path:
    """
    Descarga un archivo de Google Drive a la ruta indicada.
    Retorna la ruta del archivo descargado.
    """
    if not file_id:
        raise ValueError("file_id no puede ser None o vacío")

    logger.info("Iniciando descarga de file_id='%s' hacia '%s'", file_id, dest)

    try:
        request = drive_service.files().get_media(fileId=file_id)
        with io.FileIO(dest, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug("Progreso descarga: %.2f%%", status.progress() * 100)

        logger.info("Descarga completada: %s", dest)
        return dest

    except Exception as e:
        logger.exception("Error al descargar file_id='%s': %s", file_id, e)
        raise
