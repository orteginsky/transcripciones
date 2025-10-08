# src/domain/schemas.py
from pydantic import BaseModel, HttpUrl, AnyUrl
from typing import Optional, Literal

class AudioRequest(BaseModel):
    """
    Modelo de entrada para procesar un registro de audio.
    """
    row_number: int
    witness_name: str
    call_date: str
    psychologist: str
    audio_file_link: HttpUrl
    client_name: Optional[str] = "VAWA_Cliente"
    testimony_type: Optional[str] = "T WS"

class AudioResponse(BaseModel):
    """
    Modelo de salida estandarizado.
    """
    status: Literal["success", "error"]
    row_number: int
    message: Optional[str] = None
    transcript: Optional[str] = None
