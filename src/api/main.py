from fastapi import FastAPI
from src.api.routes import audio_pipeline
from src.logging_conf import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="TMF Audio Transcription API")

@app.on_event("startup")
def on_startup():
    logger.info("🟢 API iniciada y lista para recibir solicitudes")

# Registrar rutas
app.include_router(audio_pipeline.router, prefix="/api", tags=["Audio Pipeline"])

@app.get("/")
def root():
    return {"message": "TMF Audio Transcription API - Online"}
