# src/api/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, Literal, Dict, Any

# --- Enums y Tipos ---
BackendStrategy = Literal[
    "auto",
    "stt_v1_stereo",
    "gemini_flash",
    "gemini_pro"
]

class SheetCallbackConfig(BaseModel):
    """Configuración para escribir el resultado en una Google Sheet"""
    spreadsheet_id: str = Field(..., description="ID de la hoja de cálculo")
    sheet_name: str = Field(default="Hoja 1", description="Nombre de la pestaña")
    row_index: int = Field(..., description="Fila donde se escribirá el resultado (base 1)")
    transcript_doc_col: Optional[str] = Field(None, description="Columna para el link del Doc (ej: 'E')")
    status_col: Optional[str] = Field(None, description="Columna para status (ej: 'F')")
    engine_col: Optional[str] = Field(None, description="Columna para motor usado (ej: 'G')")
    duration_col: Optional[str] = Field(None, description="Columna para duración (ej: 'H')")

class EnqueueNextStepConfig(BaseModel):
    """Configuración genérica para encadenar CUALQUIER servicio"""
    enqueuer_url: HttpUrl = Field(..., description="URL del Enqueuer")
    target_service_name: str = Field(..., description="Nombre del servicio destino en el Enqueuer")
    payload_template: Dict[str, Any] = Field(default_factory=dict, description="Datos extra para pasar al siguiente servicio")

# --- Request Principal ---

class TranscriptionRequest(BaseModel):
    # 1. Identificación del Caso
    case_id: str = Field(..., description="ID único del caso/cliente (usado para carpetas en GCS)")
    title: str = Field(..., description="Título para el encabezado del Doc")

    # 2. Input (Fuente)
    drive_file_id: Optional[str] = Field(..., description="ID del archivo en Drive (Audio: .mp3, .wav, .m4a / Video: .mp4)")

    # 3. Output Principal (Contenedor)
    doc_id: str = Field(..., description="ID del Google Doc donde se escribirá la transcripción")

    # 4. Configuración de Procesamiento
    strategy: BackendStrategy = Field(
        default="auto",
        description="Estrategia de transcripción: 'auto' usa el router inteligente"
    )
    is_8x8_call: bool = Field(
        default=False,
        description="True si es llamada telefónica estéreo de 8x8 (fuerza STT V1)"
    )
    language_code: str = Field(default="es-MX", description="Código de idioma para STT")
    bucket_name: Optional[str] = Field(None, description="Bucket GCS (opcional, usa settings por defecto)")

    # 5. Callbacks
    sheet_callback: Optional[SheetCallbackConfig] = Field(
        None,
        description="Configuración para actualizar Google Sheets con el resultado"
    )
    next_step_task: Optional[EnqueueNextStepConfig] = None

    @field_validator('drive_file_id')
    def extract_drive_id(cls, v):
        # Si App Script manda el link completo por error, lo limpiamos
        if v and "id=" in v:
            return v.split("id=")[1].split("&")[0]
        if v and "/d/" in v:
            return v.split("/d/")[1].split("/")[0]
        return v

# --- Responses ---

class TranscriptionResponse(BaseModel):
    case_id: str
    doc_id: str
    backend_used: str
    duration_seconds: float
    status: Literal["success", "error"]
    timestamp: str
    output_files: Dict[str, str] = Field(default_factory=dict)

class ErrorResponse(BaseModel):
    detail: str
    code: str
