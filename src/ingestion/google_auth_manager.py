# src/ingestion/google_auth_manager.py
import os
from src.logging_conf import get_logger

logger = get_logger(__name__)

def get_drive_docs():
    """
    Devuelve (drive_service, docs_service, creds).
    Usa Service Account si GOOGLE_APPLICATION_CREDENTIALS está definida;
    de lo contrario, usa OAuth local.
    """
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        from src.ingestion.auth_service import get_google_creds_service
        sheets_service, drive_service, docs_service, creds = get_google_creds_service()
        logger.info("🔐 Autenticación: Service Account")
        return drive_service, docs_service, creds
    else:
        from src.ingestion.auth import get_google_creds
        sheets_service, drive_service, docs_service, creds = get_google_creds()
        logger.info("🧑‍💻 Autenticación: OAuth local")
        return drive_service, docs_service, creds
