# src/domain/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class TranscriptionRequest(BaseModel):
    case_id: str
    title: str
    media_link: Optional[str] = None
    audio_link: Optional[str] = None  # retro-compat si aún lo usas en otros sitios
    doc_id: str
    language_code: Optional[str] = Field(default="es-ES")
    diarization: Optional[bool] = False
    model: Optional[str] = "latest_long"

class TranscriptionResponse(BaseModel):
    case_id: str
    title: str
    backend: str
    doc_id: str
    duration_ms: int
    timestamp: str

class ErrorResponse(BaseModel):
    error: Dict[str, Any]
