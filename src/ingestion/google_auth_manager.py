# src/ingestion/google_auth_manager.py
import os
from src.logging_conf import get_logger

logger = get_logger(__name__)

def get_google_services():
    """
    Devuelve (sheets_service, drive_service, docs_service, creds).
    Detecta si usar OAuth local o Service Account automáticamente.
    """
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            from src.ingestion.auth import get_google_creds
            logger.info("🧑‍💻 Usando autenticación OAuth local (token.json).")
            sheets_service, drive_service, docs_service, creds = get_google_creds()
            return drive_service, docs_service, creds
        except Exception as e:
            logger.exception("Error con OAuth local: %s", e)
            raise
    else:
        try:
            from src.ingestion.auth_service import get_google_creds_service
            logger.info("🔐 Usando Service Account (GOOGLE_APPLICATION_CREDENTIALS).")
            sheets_service, drive_service, docs_service, creds = get_google_creds_service()
            return drive_service, docs_service, creds
        except Exception as e:
            logger.exception("Error con Service Account: %s", e)
            raise
