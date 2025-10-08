from fastapi import APIRouter, HTTPException
from src.domain.schemas import AudioRequest, AudioResponse
from src.logging_conf import get_logger
from src.storage.upload_service import save_drive_audio_to_gcs

logger = get_logger(__name__)
router = APIRouter(prefix="/audio", tags=["Audio Processing"])

@router.post("/upload", response_model=AudioResponse)
def upload_audio_to_bucket(req: AudioRequest):
    """
    Descarga el audio de Drive y lo sube al bucket GCS.
    """
    try:
        logger.info("Iniciando carga GCS para fila=%s (%s)", req.row_number, req.witness_name)
        link = str(req.audio_file_link)
        gcs_uri = save_drive_audio_to_gcs(link, f"{req.row_number}_{req.witness_name}")

        return AudioResponse(
            status="success",
            row_number=req.row_number,
            message=f"Audio subido correctamente para {req.witness_name}",
            transcript=gcs_uri  # aquí usamos 'transcript' temporalmente para devolver la URI
        )

    except Exception as e:
        logger.exception("Error subiendo audio a GCS (fila %s): %s", req.row_number, e)
        raise HTTPException(status_code=500, detail=str(e))
