# tests/test_drive_list.py
from src.ingestion.google_auth_manager import get_google_services

sheets, drive, creds = get_google_services()
results = drive.files().list(pageSize=5, fields="files(id, name)").execute()
for f in results.get("files", []):
    print(f"{f['name']} ({f['id']})")
