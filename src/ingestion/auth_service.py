# src/ingestion/auth_service.py
from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.auth

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


def get_google_creds_service():
    """
    Autenticación únicamente mediante Service Account.

    Preferencia:
    1. Si existe settings.google_application_credentials, usa ese key file (desarrollo local)
    2. Si no, usa ADC (Application Default Credentials) en Cloud Run

    Returns:
        tuple: (drive_service, docs_service, creds)
    """
    try:
        gac = settings.google_application_credentials

        if gac:
            creds = service_account.Credentials.from_service_account_file(
                gac,
                scopes=SCOPES,
            )
            logger.info("🔐 Autenticación con Service Account (key file): %s", gac)
        else:
            creds, _ = google.auth.default(scopes=SCOPES)
            logger.info("🔐 Autenticación con ADC (runtime service account)")

        drive_service = build("drive", "v3", credentials=creds)
        docs_service = build("docs", "v1", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        sa_email = getattr(creds, "service_account_email", "N/A")
        logger.info("✅ Service Account activa: %s", sa_email)

        return drive_service, docs_service, sheets_service, creds

    except Exception as e:
        logger.exception("❌ Error autenticando con service account: %s", e)
        raise
