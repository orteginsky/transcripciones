# src/ingestion/auth_service.py
# Librerias externas
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Módulos Globales
from src.settings import GOOGLE_APPLICATION_CREDENTIALS
from src.logging_conf import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents"
]


def get_google_creds_service():
    """
    Autenticación con cuenta de servicio (sin navegador).
    Devuelve los servicios de Sheets, Drive, Docs y las credenciales.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_APPLICATION_CREDENTIALS,
            scopes=SCOPES,
        )
        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        docs_service = build("docs", "v1", credentials=creds)
        logger.info("Autenticación con service account exitosa.")
        return sheets_service, drive_service, docs_service, creds
    except Exception as e:
        logger.exception("Error autenticando con service account: %s", e)
        raise
