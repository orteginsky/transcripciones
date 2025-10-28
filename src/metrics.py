# src/metrics.py
from prometheus_client import Counter, Histogram

# ⚠️ Mantén pocas labels y valores de baja cardinalidad
TRANSCRIPTIONS_TOTAL = Counter(
    "transcriptions_total",
    "Transcripciones completadas por backend",
    ["backend"]  # valores esperados: gemini_vertex, stt_v2
)

TRANSCRIPTIONS_ERRORS_TOTAL = Counter(
    "transcriptions_errors_total",
    "Errores en el pipeline de transcripción",
    ["code"]  # BAD_REQUEST, STT_FAILED, INTERNAL, etc.
)

PIPELINE_DURATION_SECONDS = Histogram(
    "pipeline_duration_seconds",
    "Duración total del pipeline de transcripción",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1200)  # ajusta a tus tamaños reales
)

STT_PHASE_SECONDS = Histogram(
    "transcription_phase_seconds",
    "Duración de la fase de transcripción (Gemini/STT)",
    ["backend"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300)
)
