# src/docs/google_docs_writer.py
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.ingestion.google_auth_manager import get_google_services
from src.logging_conf import get_logger
from src.settings import GCP_PROJECT_ID, SERVICE_ACCOUNT_SANDBOX_FOLDER

logger = get_logger(__name__)

def create_google_doc_from_transcript(title: str, transcript_text: str) -> str:
    """
    Crea un documento de Google Docs (con o sin carpeta padre) usando la API de Drive + Docs.
    Soporta tanto credenciales OAuth como Service Account.
    - Si la carpeta tiene espacio -> guarda ahí.
    - Si falla por 'storageQuotaExceeded' -> guarda en el Drive interno de la Service Account.
    - Devuelve siempre un enlace público editable.
    """
    try:
        # 🔑 Obtener credenciales activas
        drive_service, docs_service, creds = get_google_services()
        
        docs_service = build("docs", "v1", credentials=creds)

        # 1️⃣ Crear documento base desde Drive (más estable que desde Docs)
        file_metadata = {
            "name": title,
            "parents": [SERVICE_ACCOUNT_SANDBOX_FOLDER],
            "mimeType": "application/vnd.google-apps.document"
        }

        try:
            file = drive_service.files().create(
                body=file_metadata,
                fields="id, webViewLink"
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and "storageQuotaExceeded" in str(e):
                logger.warning("⚠️ Cuota llena en la carpeta. Creando documento en el Drive interno de la cuenta de servicio...")
                # Reintentar sin carpeta
                file_metadata.pop("parents", None)
                file = drive_service.files().create(
                    body=file_metadata,
                    fields="id, webViewLink"
                ).execute()
            else:
                raise

        doc_id = file["id"]
        logger.info(f"✅ Documento creado: {doc_id}")

        # 2️⃣ Agregar texto básico
        try:
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": transcript_text or "Documento generado automáticamente."
                            }
                        }
                    ]
                }
            ).execute()
        except HttpError as e:
            logger.warning(f"⚠️ Error insertando texto (puede ser formato o tamaño): {e}")

        # 3️⃣ Compartir documento públicamente (editable)
        try:
            drive_service.permissions().create(
                fileId=doc_id,
                body={"type": "anyone", "role": "writer"},
                fields="id"
            ).execute()
        except HttpError as e:
            logger.warning(f"⚠️ No se pudieron establecer permisos públicos: {e}")

        # 4️⃣ Enlace final
        public_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info(f"📄 Documento disponible públicamente en: {public_url}")

        return public_url

    except HttpError as e:
        if e.resp.status == 403 and "SERVICE_DISABLED" in str(e):
            logger.error("🚨 La API de Google Docs no está habilitada.")
            logger.error(f"Actívala en: https://console.developers.google.com/apis/api/docs.googleapis.com/overview?project={GCP_PROJECT_ID}")
        else:
            logger.error(f"❌ Error al crear el documento: {e}")
        raise

    except Exception as e:
        logger.exception(f"❌ Error inesperado al crear el documento: {e}")
        raise
