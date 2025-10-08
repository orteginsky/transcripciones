# src/storage/drive_uploader.py
import os
from googleapiclient.http import MediaFileUpload
from src.ingestion.auth_service import get_google_creds_service
from src.logging_conf import get_logger

logger = get_logger(__name__)

# Puedes configurar esta variable en .env
# o mantenerla fija para tus pruebas iniciales
TRANSCRIPTION_DRIVE_FOLDER_ID = os.getenv("TRANSCRIPTION_DRIVE_FOLDER_ID", "1ky3nMJw8yxot9h4UU6c6rXnOkg32X_rf")

def upload_file_to_drive(file_path: str, folder_id: str | None = TRANSCRIPTION_DRIVE_FOLDER_ID) -> str | None:
    """
    Sube un archivo a una carpeta específica de Google Drive.
    Devuelve el enlace compartible (webViewLink).
    """
    sheets_service, drive_service, _ = get_google_creds_service()
    file_name = os.path.basename(file_path)
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    
    logger.info(f"📤 Subiendo '{file_name}' a Google Drive (carpeta ID: {folder_id})...")

    try:
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, parents'
        ).execute()

        # 🔓 Compartir con todos los que tengan el enlace (modo lector)
        try:
            drive_service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            logger.info(f"✅ Permisos públicos establecidos para '{file_name}'.")
        except Exception as perm_e:
            logger.warning(f"⚠️ No se pudieron establecer permisos públicos para '{file_name}': {perm_e}")

        web_link = file.get('webViewLink')
        logger.info(f"✅ Archivo subido exitosamente: {web_link}")
        return web_link

    except Exception as e:
        logger.exception(f"❌ Error al subir el archivo '{file_name}' a Drive: {e}")
        return None
