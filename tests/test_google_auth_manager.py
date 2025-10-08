# tests/test_google_auth_manager.py
from src.ingestion.google_auth_manager import get_google_services

def test_google_auth():
    sheets, drive, creds = get_google_services()
    assert creds.service_account_email.endswith("@ortega-473114.iam.gserviceaccount.com")
    print("✅ Autenticación exitosa con:", creds.service_account_email)

if __name__ == "__main__":
    test_google_auth()
