# src/api/main.py
# Librerias externas
from fastapi import FastAPI

# Libreria interna
import os

# Módulos
from src.api.routes import audio_pipeline

# Módulo Global
from src.logging_conf import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Definir lifespan primero
async def lifespan(app: FastAPI):
    logger.info("🟢 API iniciada y lista para recibir solicitudes")
    yield
    logger.info("🔴 API cerrada y lista para ser reiniciada")

# Crear la aplicación FastAPI
app = FastAPI(title="TMF Audio Transcription API", lifespan=lifespan)

# Registrar rutas
app.include_router(audio_pipeline.router, prefix="/api", tags=["Audio Pipeline"])

@app.get("/")
def root():
    return {"message": "TMF Audio Transcription API - Online"}
