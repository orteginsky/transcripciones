# tests/test_service_account_docs_creation.py
from src.ingestion.google_auth_manager import get_google_services
from googleapiclient.discovery import build

if __name__ == "__main__":
    PARENT_FOLDER_ID = "1T3mxaJahqUc455W1-1VCiYYEra6PO03_"
    
    print("🤖 Probando creación de documento con Service Account...")

    drive_service, docs_service, creds = get_google_services()
    docs_service = build("docs", "v1", credentials=creds)

    # 1️⃣ Crear el archivo DOCS directamente en Drive
    file_metadata = {
        "name": "Prueba Service Account TMF",
        "parents": [PARENT_FOLDER_ID],
        "mimeType": "application/vnd.google-apps.document"
    }

    file = drive_service.files().create(body=file_metadata, fields="id, webViewLink").execute()
    doc_id = file["id"]

    print("✅ Documento creado en Drive:", file["webViewLink"])

    # 2️⃣ Escribir contenido dentro del documento con la API de Docs
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {"insertText": {
                    "location": {"index": 1},
                    "text": "Documento creado automáticamente por Service Account TMF."
                }}
            ]
        }
    ).execute()

    # 3️⃣ Compartir públicamente (opcional)
    drive_service.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "writer"}
    ).execute()

    print("📄 Documento disponible en:")
    print(f"https://docs.google.com/document/d/{doc_id}/edit")
