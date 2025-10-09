from fastapi import FastAPI
from src.api.routes import audio_pipeline
from src.logging_conf import setup_logging, get_logger
import os

setup_logging()
logger = get_logger(__name__)

# Crear la aplicación FastAPI
app = FastAPI(title="TMF Audio Transcription API", lifespan=lifespan)

# Modificación de la lógica de arranque usando lifespan (nuevo enfoque)
async def lifespan(app: FastAPI):
    logger.info("🟢 API iniciada y lista para recibir solicitudes")
    yield
    logger.info("🔴 API cerrada y lista para ser reiniciada")

# Registrar rutas
app.include_router(audio_pipeline.router, prefix="/api", tags=["Audio Pipeline"])

@app.get("/")
def root():
    return {"message": "TMF Audio Transcription API - Online"}

