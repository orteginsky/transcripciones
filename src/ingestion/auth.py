# src/ingestion/auth.py
# Librerias externas
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Librerias internas
import os

# Módulos globales
from src.logging_conf import get_logger
from src.settings import GOOGLE_OAUTH_CREDENTIALS_FILE, GOOGLE_OAUTH_TOKEN_FILE

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",  # ✅ suficiente para leer/escribir Docs
]


def get_google_creds():
    """
    Flujo OAuth interactivo (para desarrollo).
    Crea o refresca token.json, y construye servicios de Drive, Sheets y Docs.
    """
    creds = None
    if GOOGLE_OAUTH_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(GOOGLE_OAUTH_TOKEN_FILE), SCOPES)
            logger.info("Credenciales cargadas desde token.json.")
        except Exception as e:
            logger.warning(f"Error al cargar token.json ({e}), se reautenticará.")
            GOOGLE_OAUTH_TOKEN_FILE.unlink(missing_ok=True)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Token refrescado exitosamente.")
            except Exception as e:
                logger.error(f"No se pudo refrescar token: {e}")
                creds = None

        if not creds:
            logger.info("Iniciando flujo OAuth local...")
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_OAUTH_CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            with open(GOOGLE_OAUTH_TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            logger.info("Token guardado en token.json.")

    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)
    return sheets_service, drive_service, docs_service, creds
