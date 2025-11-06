# src/domain/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

TranscriberLiteral = Literal["gemini_vertex", "stt_v2"]  # amplía en el futuro

class TranscriptionRequest(BaseModel):
    case_id: str
    title: str
    media_link: Optional[str] = None
    audio_link: Optional[str] = None  # retro-compat si aún lo usas en otros sitios
    doc_id: str
    language_code: Optional[str] = Field(default="es-ES")
    diarization: Optional[bool] = False
    model: Optional[str] = "latest_long"
    transcriber: Optional[TranscriberLiteral] = None  # 👈 nuevo (override opcional)

class TranscriptionResponse(BaseModel):
    case_id: str
    title: str
    backend: str
    doc_id: str
    duration_ms: int
    timestamp: str

class ErrorResponse(BaseModel):
    error: Dict[str, Any]

class TranscribeAndDriveRequest(BaseModel):
    case_id: str
    title: str
    media_link: str          # enlace de Drive al audio (como en el endpoint actual)
    doc_id: str              # ID del Google Doc destino (para humanos)
    drive_folder_id: str     # ID de la carpeta de Drive donde guardar el .txt
    language_code: Optional[str] = None
    diarization: Optional[bool] = None
    model: Optional[str] = None
    transcriber: Optional[str] = None
