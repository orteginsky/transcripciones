# src/storage/upload_service.py
import os
import tempfile
from pathlib import Path

# Módulos Internos
from src.ingestion.drive_loader import extract_drive_id, download_from_drive
from src.ingestion.auth_service import get_google_creds_service
from src.storage.gcs_uploader import upload_to_gcs

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def save_drive_audio_to_gcs(audio_link: str, case_id: str) -> str:
    """
    Descarga un archivo de audio o video desde Google Drive a RAM (/tmp),
    lo sube a GCS y limpia la memoria inmediatamente.

    Args:
        audio_link: Link o ID del archivo en Google Drive
        case_id: ID del caso para nombrar el archivo

    Returns:
        URI del archivo en GCS (gs://bucket/path)
    """
    # 1. Autenticación y Extracción ID
    drive_service, _, _, _ = get_google_creds_service()
    file_id = extract_drive_id(audio_link)

    if not file_id:
        raise ValueError(f"No se pudo extraer file_id del enlace: {audio_link}")

    # 2. Context Manager: Crea carpeta en /tmp (RAM) y la autodestruye al salir
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = None
        
        try:
            # --- Paso A: Obtener Metadata para extensión correcta ---
            try:
                file_metadata = drive_service.files().get(
                    fileId=file_id,
                    fields="name,mimeType"
                ).execute()

                original_name = file_metadata.get("name", f"{case_id}")
                mime_type = file_metadata.get("mimeType", "")
                
                # Mapeo extendido de MimeTypes
                mime_to_ext = {
                    "audio/mpeg": ".mp3",
                    "audio/mp3": ".mp3",
                    "audio/wav": ".wav",
                    "audio/x-wav": ".wav",
                    "audio/x-m4a": ".m4a",
                    "audio/mp4": ".m4a",
                    "audio/flac": ".flac",
                    "audio/ogg": ".ogg",
                    "video/mp4": ".mp4",
                    "video/mpeg": ".mpeg",
                    "video/quicktime": ".mov"
                }

                # Determinar extensión
                if "." in original_name:
                    ext = Path(original_name).suffix
                else:
                    ext = mime_to_ext.get(mime_type, ".mp3") # Fallback a mp3

                local_path = Path(tmpdir) / f"{case_id}{ext}"
                logger.info(f"📥 Metadata obtenida: {original_name} ({mime_type}) -> Guardando como {local_path.name}")

            except Exception as e:
                logger.warning(f"⚠️ Fallo al obtener metadata (usando fallback .mp3): {e}")
                local_path = Path(tmpdir) / f"{case_id}.mp3"

            # --- Paso B: Descargar (Ocupa RAM) ---
            logger.info(f"⬇️ Iniciando descarga a memoria temporal...")
            download_from_drive(drive_service, file_id, local_path)
            
            file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
            logger.info(f"✅ Descarga completada en RAM ({file_size_mb:.2f} MB)")

            # --- Paso C: Subir a GCS ---
            logger.info(f"⬆️ Subiendo a GCS...")
            gcs_uri = upload_to_gcs(local_path)

            if not gcs_uri:
                raise ValueError("La subida a GCS retornó URI vacía")

            return gcs_uri

        except Exception as e:
            logger.error(f"❌ Error en save_drive_audio_to_gcs: {e}")
            raise e

        finally:
            # --- Paso D: Limpieza Explícita (Para liberar RAM antes de salir del bloque) ---
            # Aunque TemporaryDirectory lo hace al final, forzarlo aquí asegura
            # que si hubo una excepción arriba, liberamos memoria ANTES de propagar el error.
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    logger.info(f"🧹 Archivo temporal eliminado de RAM: {local_path.name}")
                except Exception as clean_err:
                    logger.warning(f"⚠️ No se pudo borrar archivo temporal manualmente: {clean_err}")
            
            # Al salir de este bloque 'with', la carpeta 'tmpdir' también se borra.