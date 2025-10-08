# src/maintenance/limpia_drive.py
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.logging_conf import get_logger, setup_logging
from src.settings import GOOGLE_APPLICATION_CREDENTIALS

setup_logging("INFO")
logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def clear_service_account_drive(delete: bool = False, limit: int = 50):
    """
    Lista (y opcionalmente elimina) archivos creados por la cuenta de servicio en su Drive.

    Args:
        delete (bool): Si es True, elimina los archivos listados.
        limit (int): Máximo de archivos a listar/eliminar.
    """
    try:
        if not GOOGLE_APPLICATION_CREDENTIALS or not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
            logger.error("❌ No se encontró el archivo de credenciales definido en GOOGLE_APPLICATION_CREDENTIALS.")
            return

        logger.info("🔐 Cargando credenciales de Service Account...")
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
        )
        drive_service = build("drive", "v3", credentials=creds)

        logger.info("📂 Listando archivos en el Drive de la Service Account...")
        results = drive_service.files().list(
            pageSize=limit,
            fields="files(id, name, mimeType, createdTime)"
        ).execute()
        items = results.get("files", [])

        if not items:
            logger.info("✅ No se encontraron archivos en el Drive de la Service Account.")
            return

        logger.info(f"📄 Se encontraron {len(items)} archivos:")

        for i, item in enumerate(items, start=1):
            name = item.get("name")
            file_id = item.get("id")
            mime_type = item.get("mimeType")
            created = item.get("createdTime")

            logger.info(f"{i}. {name} ({mime_type}) - Creado: {created}")

            if delete:
                try:
                    drive_service.files().delete(fileId=file_id).execute()
                    logger.info(f"🗑️ Archivo eliminado: {name}")
                except HttpError as e:
                    logger.warning(f"⚠️ No se pudo eliminar {name}: {e}")

        if delete:
            logger.info("✅ Limpieza completada correctamente.")
        else:
            logger.info("👀 Modo solo lectura: no se eliminaron archivos.")

    except Exception as e:
        logger.exception(f"❌ Error al limpiar el Drive de la Service Account: {e}")


if __name__ == "__main__":
    mode = os.getenv("DELETE_MODE", "true").lower() == "true"
    clear_service_account_drive(delete=mode)
