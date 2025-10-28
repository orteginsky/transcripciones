# src/ingestion/auth_service.py
from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.auth

from src.logging_conf import get_logger
logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

def get_google_creds_service():
    """
    Preferir ADC (Cloud Run con --service-account). Si existe
    GOOGLE_APPLICATION_CREDENTIALS, usa ese key file (compat local).
    Devuelve (drive_service, docs_service, creds).
    """
    try:
        import os
        gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if gac:
            creds = service_account.Credentials.from_service_account_file(gac, scopes=SCOPES)
            logger.info("Auth con Service Account (key file).")
        else:
            creds, _ = google.auth.default(scopes=SCOPES)
            logger.info("Auth con ADC (runtime service account).")

        drive_service = build("drive", "v3", credentials=creds)
        docs_service  = build("docs", "v1",  credentials=creds)
        return drive_service, docs_service, creds
    except Exception as e:
            logger.exception("Error autenticando con service account: %s", e)
            raise

