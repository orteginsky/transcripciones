# src/orchestration/runner.py
"""
Orquestador Principal del Pipeline de Transcripción.
Este módulo coordina todo el flujo de trabajo:
    1. Descarga de archivos desde Drive
    2. Routing inteligente (decide qué motor usar)
    3. Normalización condicional de audio
    4. Transcripción (STT V1 o Gemini Flash)
    5. Escritura en Google Docs
    6. Callbacks a Google Sheets
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
from pathlib import PurePosixPath
import time
import os
import mimetypes
import requests

from google.cloud import storage

# Módulos Internos
from src.logging_conf import get_logger
from src.settings import settings
from src.api.schemas import TranscriptionRequest

# Router Inteligente
from src.orchestration.router import decide_transcription_strategy, should_normalize_audio

# Servicios de Infraestructura
from src.storage.upload_service import save_drive_audio_to_gcs
from src.storage.audio_normalizer_service import normalize_and_upload_gcs
from src.storage.gcs_cleaner import delete_gcs_files

# Servicios de Transcripción
from src.transcription.transcribers import transcribe_from_gcs_uri as transcribe_stt_v1
from src.transcription.vertex_service import transcribe_with_gemini
from src.docs.google_docs_service import append_formatted_transcript
from src.sheets.sheets_service import update_row_status, update_transcription_result

# Métricas
from src.metrics import (
    TRANSCRIPTIONS_TOTAL,
    TRANSCRIPTIONS_ERRORS_TOTAL,
    PIPELINE_DURATION_SECONDS,
    STT_PHASE_SECONDS
)

logger = get_logger(__name__)

class PipelineError(Exception):
    """Error personalizado del pipeline con código de error"""
    def __init__(self, message: str, code: str = "INTERNAL"):
        self.message = message
        self.code = code
        super().__init__(self.message)


def _ensure_storage_client():
    """Configura y retorna el cliente de Google Cloud Storage"""
    if settings.google_application_credentials and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        if os.path.exists(settings.google_application_credentials):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    return storage.Client(project=settings.gcp_project_id)


def _parse_gemini_output(text: str) -> str:
    """
    Convierte la salida Markdown de Gemini al formato interno |SEPARATOR|
    usado por el sistema de documentos.
    """
    text = text.replace("**", "")
    formatted_blocks = []
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            # Búsqueda heurística de hablante
            parts = line.split(":", 1)
            speaker_info = parts[0].strip()
            content = parts[1].strip()
            formatted_blocks.append(f"{speaker_info}:|SEPARATOR|{content}")
        else:
            formatted_blocks.append(f"{line}")

    return "\n\n".join(formatted_blocks)


def _guess_mime_type(gcs_uri: str) -> str:
    """Adivina el tipo MIME basado en la extensión para Vertex AI."""
    mime, _ = mimetypes.guess_type(gcs_uri)
    if not mime:
        # Fallbacks comunes si mimetypes falla
        if gcs_uri.endswith(".mp3"):
            return "audio/mpeg"
        if gcs_uri.endswith(".wav"):
            return "audio/wav"
        if gcs_uri.endswith(".m4a"):
            return "audio/mp4"
        if gcs_uri.endswith(".mp4"):
            return "video/mp4"
        if gcs_uri.endswith(".flac"):
            return "audio/flac"
        return "audio/mpeg"  # Default genérico
    return mime


def _format_engine_name(engine: str) -> str:
    """Formatea el nombre del motor para visualización"""
    engine_names = {
        "stt_v1": "STT V1 Stereo",
        "gemini_flash": "gemini-3-flash-preview",
        "gemini_pro": "Gemini 2.5 Pro"
    }
    return engine_names.get(engine, engine)


# ==============================================================================
# ORQUESTADOR PRINCIPAL
# ==============================================================================

def run_transcription_pipeline(request: TranscriptionRequest) -> Dict[str, Any]:
    """
    Orquesta todo el proceso de transcripción con routing inteligente.

    Flujo:
    1. Descarga archivo de Drive → GCS (raw)
    2. Router decide estrategia (STT V1 vs Gemini)
    3. Normalización condicional (solo si es necesario)
    4. Transcripción con motor seleccionado
    5. Escritura en Google Docs
    6. Callbacks a Google Sheets (status, motor, duración, etc.)
    7. Limpieza de archivos temporales

    Args:
        request: TranscriptionRequest con toda la configuración

    Returns:
        Dict con el resultado del pipeline
    """
    start_time = time.time()
    uris_creados: List[str] = []

    ctx = f"case={request.case_id} doc={request.doc_id}"
    logger.info(f"🚀 Iniciando Pipeline ({ctx})")

    storage_client = _ensure_storage_client()

    try:
        # ---------------------------------------------------------
        # PASO 1: Descarga de Drive
        # ---------------------------------------------------------
        drive_link = request.drive_file_id
        if "http" not in drive_link:
            drive_link = f"https://drive.google.com/uc?id={request.drive_file_id}"

        logger.info("📥 [1/5] Descargando archivo de Drive...")
        gcs_raw_uri = save_drive_audio_to_gcs(drive_link, request.case_id)
        uris_creados.append(gcs_raw_uri)
        logger.info(f"✅ Archivo en GCS: {gcs_raw_uri}")

        # ---------------------------------------------------------
        # PASO 2: Router Inteligente
        # ---------------------------------------------------------
        logger.info("🧠 [2/5] Ejecutando router inteligente...")
        if request.strategy != "auto":
            logger.info(f"⚙️ Estrategia manual: {request.strategy}")
            if request.strategy == "stt_v1_stereo":
                engine = "stt_v1"
                requires_normalization = True
                target_channels = 2
                reason = "Estrategia manual: STT V1 Stereo"
            elif "gemini" in request.strategy:
                engine = "gemini_flash"
                requires_normalization = False
                target_channels = 1
                reason = f"Estrategia manual: {request.strategy}"
            else:
                raise PipelineError(f"Estrategia no reconocida: {request.strategy}")
            
            from src.orchestration.router import RoutingDecision
            decision = RoutingDecision(engine=engine, requires_normalization=requires_normalization, target_channels=target_channels, reason=reason)
        else:
            decision = decide_transcription_strategy(request, gcs_raw_uri)

        logger.info(f"✅ Motor seleccionado: {_format_engine_name(decision.engine)}")

        # ---------------------------------------------------------
        # PASO 3: Normalización
        # ---------------------------------------------------------
        logger.info("🎛️ [3/5] Evaluando necesidad de normalización...")
        gcs_input_uri = gcs_raw_uri 

        if decision.requires_normalization:
            logger.info(f"🔧 Normalizando audio (canales: {decision.target_channels})...")
            if decision.engine == "stt_v1":
                gcs_input_uri = normalize_and_upload_gcs(
                    gcs_raw_uri, request.case_id,
                    bucket_name=request.bucket_name or settings.gcs_bucket,
                    target_format="flac", target_channels=decision.target_channels,
                    auto_sr=True, force_normalize=True
                )
            else:
                if should_normalize_audio(decision, gcs_raw_uri):
                    gcs_input_uri = normalize_and_upload_gcs(
                        gcs_raw_uri, request.case_id,
                        bucket_name=request.bucket_name or settings.gcs_bucket,
                        target_format="mp3", target_channels=1,
                        auto_sr=False, force_normalize=False
                    )
            if gcs_input_uri != gcs_raw_uri:
                uris_creados.append(gcs_input_uri)
                logger.info(f"✅ Audio normalizado: {gcs_input_uri}")
        else:
            logger.info("⚡ Bypass de normalización - usando archivo raw")

        # ---------------------------------------------------------
        # PASO 4: Transcripción
        # ---------------------------------------------------------
        logger.info(f"📝 [4/5] Transcribiendo con {_format_engine_name(decision.engine)}...")
        stt_start = time.time()
        transcription_text = ""

        if decision.engine == "stt_v1":
            transcription_text = transcribe_stt_v1(gcs_input_uri, language_code=request.language_code)
        elif decision.engine in ["gemini_flash", "gemini_pro"]:
            model_name = settings.gemini_vertex 
            mime_type = _guess_mime_type(gcs_input_uri)
            logger.info(f"📤 Enviando a Gemini (mime: {mime_type})")
            raw_gemini_text = transcribe_with_gemini(gcs_input_uri, model_name=model_name, mime_type=mime_type, language_code=request.language_code)
            transcription_text = _parse_gemini_output(raw_gemini_text)
        else:
            raise PipelineError(f"Motor no implementado: {decision.engine}")

        stt_duration = time.time() - stt_start
        STT_PHASE_SECONDS.labels(backend=decision.engine).observe(stt_duration)

        if not transcription_text.strip():
            raise PipelineError("La transcripción resultó vacía.", code="STT_FAILED")

        # Guardar respaldo TXT
        try:
            _, key = gcs_input_uri.replace("gs://", "").split("/", 1)
            stem = PurePosixPath(key).stem
            txt_blob_path = f"transcripts/{request.case_id}/{stem}_{decision.engine}.txt"
            bucket = storage_client.bucket(request.bucket_name or settings.gcs_bucket)
            bucket.blob(txt_blob_path).upload_from_string(transcription_text, content_type="text/plain")
            logger.info(f"💾 Respaldo TXT guardado: gs://{bucket.name}/{txt_blob_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo guardar respaldo TXT: {e}")

        # ---------------------------------------------------------
        # PASO 5: Google Docs
        # ---------------------------------------------------------
        logger.info("📄 [5/5] Escribiendo en Google Docs...")
        append_formatted_transcript(doc_id=request.doc_id, title=request.title, transcript_text=transcription_text)
        doc_url = f"https://docs.google.com/document/d/{request.doc_id}/edit"
        logger.info(f"✅ Doc actualizado: {doc_url}")

        # Callbacks Sheets
        if request.sheet_callback:
            logger.info("📊 Actualizando Google Sheets...")
            cb = request.sheet_callback
            update_data = {
                "doc_url": doc_url, "status": "✅ Transcrito",
                "engine": _format_engine_name(decision.engine),
                "duration_seconds": time.time() - start_time,
                "transcript_doc_col": cb.transcript_doc_col, "status_col": cb.status_col
            }
            try:
                update_transcription_result(cb.spreadsheet_id, cb.sheet_name, cb.row_index, update_data)
            except Exception as e:
                logger.error(f"❌ Error actualizando Sheets: {e}")

        # Limpieza
        logger.info("🧹 Limpiando archivos temporales...")
        delete_gcs_files(uris_creados)

        # Métricas
        total_duration = time.time() - start_time
        PIPELINE_DURATION_SECONDS.observe(total_duration)
        TRANSCRIPTIONS_TOTAL.labels(backend=decision.engine).inc()

        # ---------------------------------------------------------
        # PASO 6: ENCOLAR SIGUIENTE SERVICIO (Generic Chaining)
        # ---------------------------------------------------------
        if request.next_step_task:
            next_step = request.next_step_task
            logger.info(f"🔄 Encolando siguiente paso hacia: {next_step.target_service_name}")
            
            # 1. Copiar plantilla original
            next_payload = next_step.payload_template.copy()
            
            # 2. Inyectar resultados estándar
            next_payload.update({
                "transcription_doc_id": request.doc_id,
                "transcription_doc_url": doc_url,
                "case_id": request.case_id,
                "source_file_id": request.drive_file_id,
                "status": "transcription_completed"
            })
            
            # 3. Empaquetar para Enqueuer
            enqueuer_payload = {
                "service": next_step.target_service_name,
                "payload": next_payload
            }
            
            try:
                # Usamos la librería 'requests' importada al inicio
                response = requests.post(
                    str(next_step.enqueuer_url),
                    json=enqueuer_payload,
                    timeout=10 
                )
                response.raise_for_status()
                logger.info(f"✅ Tarea para '{next_step.target_service_name}' encolada.")
            except Exception as e:
                # Loggeamos error pero NO detenemos el pipeline, ya que la transcripción fue exitosa
                logger.error(f"❌ Error al encolar siguiente paso: {e}")

        # FINAL
        logger.info(f"🎉 Pipeline completado exitosamente en {total_duration:.1f}s")

        return {
            "case_id": request.case_id,
            "doc_id": request.doc_id,
            "doc_url": doc_url,
            "status": "success",
            "backend_display_name": _format_engine_name(decision.engine),
            "backend_used": decision.engine,
            "duration_seconds": total_duration,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Error en Pipeline: {e}", exc_info=True)
        TRANSCRIPTIONS_ERRORS_TOTAL.labels(code=getattr(e, 'code', 'INTERNAL')).inc()
        if request.sheet_callback and request.sheet_callback.status_col:
            try:
                cb = request.sheet_callback
                update_row_status(cb.spreadsheet_id, cb.sheet_name, cb.row_index, cb.status_col, f"❌ Error: {str(e)[:100]}")
            except Exception:
                pass
        raise e