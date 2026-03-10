# src/api/main.py
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

# --- CORRECCIÓN DE IMPORTS ---
# Importamos SOLO el router desde el archivo específico
from src.api.routes import router as audio_router
from src.api.error_handler import register_exception_handlers
from src.logging_conf import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verificar credenciales al inicio
    try:
        from src.ingestion.auth_service import get_google_creds_service
        _, _, _, creds = get_google_creds_service()
        sa_email = getattr(creds, "service_account_email", "N/A")
        logger.info(f"🟢 API iniciada (Service Account: {sa_email}) | Motor: STT v1")
    except Exception as e:
        logger.warning(f"⚠️ API iniciada pero auth check falló: {e}")
    yield
    logger.info("🔴 API cerrada")

app = FastAPI(title="TMF Audio Transcription API", version="v2.0", lifespan=lifespan)

# Instrumentación Prometheus
if os.getenv("METRICS_ENABLED", "true").lower() == "true":
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Registrar Manejadores de Error
register_exception_handlers(app)

# --- REGISTRO DE RUTAS ---
# Usamos el router importado correctamente
app.include_router(audio_router, tags=["Transcription"])

@app.get("/")
def root():
    return {"message": "TMF Audio Transcription API (STT v1) - Online"}

@app.get("/health")
def health_check():
    return {"status": "ok", "engine": "stt_v1"}

@app.get("/whoami")
def whoami():
    try:
        from src.ingestion.auth_service import get_google_creds_service
        _, _, _, creds = get_google_creds_service()
        return {
            "auth_mode": "oauth2",
            "principal": getattr(creds, "client_id", "unknown"),
            "valid": getattr(creds, "valid", None),
            "engine": "stt_v1"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})