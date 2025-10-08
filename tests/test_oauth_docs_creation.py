# tests/test_oauth_docs_creation.py
from src.ingestion.auth import get_google_creds

if __name__ == "__main__":
    print("🧠 Iniciando prueba de autenticación OAuth local...")
    sheets_service, drive_service, docs_service, creds = get_google_creds()

    # 1️⃣ Crear un documento vacío
    doc = docs_service.documents().create(body={"title": "Prueba OAuth TMF"}).execute()
    doc_id = doc.get("documentId")
    print(f"✅ Documento creado. ID: {doc_id}")

    # 2️⃣ Agregar texto básico
    requests = [
        {"insertText": {"location": {"index": 1}, "text": "Hola desde la API de Google Docs 👋\n"}}
    ]
    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print("📝 Texto agregado correctamente.")

    # 3️⃣ Generar enlace
    public_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print("📄 Documento disponible en:\n", public_url)

    # 4️⃣ (Opcional) Dar permisos de lectura pública
    permission = {"type": "anyone", "role": "reader"}
    drive_service.permissions().create(fileId=doc_id, body=permission).execute()
    print("🌍 Permisos públicos aplicados.")
