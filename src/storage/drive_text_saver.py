# src/storage/driver_text_saver
from __future__ import annotations
import io
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from src.logging_conf import get_logger
from src.ingestion.auth_service import get_google_creds_service

logger = get_logger(__name__)

def _build_drive_service():
    _, _, creds = get_google_creds_service()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def save_transcript_txt_to_drive(
    *,
    text: str,
    case_id: str,
    folder_id: str,
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Crea un .txt en la carpeta de Drive indicada (Mi unidad o Shared Drive)."""
    service = _build_drive_service()

    # timezone-aware (evitamos utcnow)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_title = (title or "transcript").strip().replace("/", "-").replace("\\", "-")
    filename = f"{case_id}__{safe_title}__{ts}.txt"

    media = MediaIoBaseUpload(
        io.BytesIO(text.encode("utf-8")),
        mimetype="text/plain",
        resumable=False
    )

    created = service.files().create(
        body={"name": filename, "mimeType": "text/plain", "parents": [folder_id]},
        media_body=media,
        fields="id, webViewLink, name",
        supportsAllDrives=True,
    ).execute()

    logger.info("TXT guardado en Drive: id=%s name=%s", created.get("id"), created.get("name"))
    return {
        "file_id": created.get("id"),
        "webViewLink": created.get("webViewLink"),
        "name": created.get("name"),
    }
