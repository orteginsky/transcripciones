# src/api/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.routes import audio_pipeline
from src.api.middleware.error_handler import register_exception_handlers
from src.logging_conf import setup_logging, get_logger

# 👇 Prometheus (ya instalado)
from prometheus_fastapi_instrumentator import Instrumentator
import os

setup_logging()
logger = get_logger(__name__)

# Lifespan solo para logs/diagnóstico (sin instrumentación aquí)
async def lifespan(app: FastAPI):
    try:
        from src.ingestion.auth_service import get_google_creds_service
        drive_service, docs_service, creds = get_google_creds_service()
        sa_email = getattr(creds, "service_account_email", None)
        mode = "Service Account" if sa_email else "OAuth"
        if sa_email:
            logger.info("🟢 API iniciada y lista para recibir solicitudes (Auth: %s - %s)", mode, sa_email)
        else:
            logger.info("🟢 API iniciada y lista para recibir solicitudes (Auth: %s)", mode)
    except Exception as e:
        logger.info("🟢 API iniciada (auth check omitido: %s)", e)

    yield
    logger.info("🔴 API cerrada y lista para ser reiniciada")

app = FastAPI(title="TMF Audio Transcription API", version="v2", lifespan=lifespan)

# ✅ Instrumentar y exponer /metrics **ANTES** de que arranque la app
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() in ("1", "true", "yes")
if METRICS_ENABLED:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Handlers de error estándar
register_exception_handlers(app)

# Rutas
app.include_router(audio_pipeline.router, prefix="/api", tags=["Audio Pipeline"])

@app.get("/")
def root():
    return {"message": "TMF Audio Transcription API - Online"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/whoami")
def whoami():
    try:
        from src.ingestion.auth_service import get_google_creds_service
        drive_service, docs_service, creds = get_google_creds_service()
        sa_email = getattr(creds, "service_account_email", None)
        if sa_email:
            return {"auth_mode": "service_account", "principal": sa_email}
        return {"auth_mode": "oauth", "principal": getattr(creds, "client_id", None)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL", "message": "Unable to determine principal", "details": {"reason": str(e)}}}
        )
