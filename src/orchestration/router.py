# src/orchestration/router.py
"""
Brain/Router Logic for Transcription Pipeline

This module determines which transcription engine to use based on:
1. File type (audio vs video)
2. Audio characteristics (duration, channels)
3. Source (8x8 calls vs other sources)
"""
from __future__ import annotations
from typing import Literal
from dataclasses import dataclass
import os

from src.logging_conf import get_logger
from src.api.schemas import TranscriptionRequest

logger = get_logger(__name__)

TranscriptionEngine = Literal["stt_v1", "gemini_flash"]

@dataclass
class RoutingDecision:
    """Result of routing decision"""
    engine: TranscriptionEngine
    requires_normalization: bool
    target_channels: int
    reason: str

def decide_transcription_strategy(
    request: TranscriptionRequest,
    gcs_raw_uri: str
) -> RoutingDecision:
    """
    Brain/Router: Logica optimizada para velocidad.

    Reglas de Eficiencia:
    1. 8x8 Call -> STT V1 (Stereo forzado, Normalización Requerida).
    2. Todo lo demás -> Gemini Flash (Bypass de normalización por defecto).
    
    """

    # Regla 1: Llamadas 8x8 (Infraestructura Legacy/Stereo)
    if request.is_8x8_call:
        return RoutingDecision(
            engine="stt_v1",
            requires_normalization=True, # STT V1 EXIGE FLAC Stereo
            target_channels=2,
            reason="8x8 call detected → STT V1 (Stereo Isolation)"
        )

    # Regla 2: Fast-Track para todo lo demás (Gemini)
    # Asumimos Gemini Flash para videos, audios de drive, mp3, etc.
    # Es más barato, más rápido y soporta formatos nativos.
    return RoutingDecision(
        engine="gemini_flash",
        requires_normalization=False, # Optimización: Intentamos enviar el archivo crudo
        target_channels=1,
        reason="Default Strategy → Gemini Flash (Native format bypass)"
    )

def should_normalize_audio(decision: RoutingDecision, gcs_uri: str) -> bool:
    """
    Determina si es OBLIGATORIO normalizar.
    """
    # STT V1 siempre requiere formato estricto
    if decision.engine == "stt_v1":
        return True

    # Para Gemini, somos optimistas. Si es un formato común, NO normalizamos.
    ext = os.path.splitext(gcs_uri.lower())[1]
    
    # Lista ampliada de formatos que Gemini soporta nativamente (ahorrando tiempo de CPU)
    native_formats = {
        ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".webm", ".mov", ".mpeg"
    }

    if ext in native_formats:
        # 
        return False

    # Solo si es un formato exótico (ej: .amr, .wma) normalizamos
    logger.info(f"⚠️ Formato no nativo detectado ({ext}), se requiere normalización.")
    return True