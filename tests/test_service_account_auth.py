# tests/test_service_account_auth.py
from src.ingestion.auth_service import get_google_creds_service

if __name__ == "__main__":
    sheets, drive, docs, creds = get_google_creds_service()
    print("✅ Autenticado como:", creds.service_account_email)
