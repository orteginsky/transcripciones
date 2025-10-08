from src.ingestion.google_auth_manager import get_google_services
sheets, drive, creds = get_google_services()
print("OK", creds.service_account_email)
