# src/orchestration/router.py
"""
Brain/Router Logic for Transcription Pipeline

This module determines which transcription engine to use based on:
1. File type (audio vs video)
2. Audio characteristics (duration, channels)
3. Source (8x8 calls vs other sources)
"""
from __future__ import annotations
from typing import Literal, Optional
from dataclasses import dataclass, field
import os

from src.logging_conf import get_logger
from src.api.schemas import TranscriptionRequest

logger = get_logger(__name__)

# Umbral a partir del cual se activa la segmentación por fragmentos (20 min)
SEGMENTATION_THRESHOLD_SEC: int = 20 * 60

TranscriptionEngine = Literal["stt_v1", "gemini_flash"]

@dataclass
class RoutingDecision:
    """Result of routing decision"""
    engine: TranscriptionEngine
    requires_normalization: bool
    target_channels: int
    reason: str
    requires_segmentation: bool = field(default=False)
    duration_seconds: Optional[float] = field(default=None)

def decide_transcription_strategy(
    request: TranscriptionRequest,
    gcs_raw_uri: str,
    duration_seconds: Optional[float] = None,
) -> RoutingDecision:
    """
    Brain/Router: Siempre usa Gemini Flash.

    Regla única: Gemini Flash para TODO (8x8 o no).
    Si la duración supera 20 minutos, activa `requires_segmentation=True`
    para que el runner use el pipeline de fragmentos entrelazados.
    """
    requires_segmentation = (
        duration_seconds is not None
        and duration_seconds > SEGMENTATION_THRESHOLD_SEC
    )

    reason = "Estrategia forzada: Gemini Flash (motor único)"
    if request.is_8x8_call:
        reason += " [override de llamada 8x8]"
    if requires_segmentation:
        reason += f" | Segmentación activada (duración={duration_seconds:.0f}s > {SEGMENTATION_THRESHOLD_SEC}s)"

    logger.info(f"🚦 Router: {reason}")

    return RoutingDecision(
        engine="gemini_flash",
        requires_normalization=False,
        target_channels=1,
        reason=reason,
        requires_segmentation=requires_segmentation,
        duration_seconds=duration_seconds,
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