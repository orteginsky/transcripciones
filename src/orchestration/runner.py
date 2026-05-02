# src/orchestration/runner.py
"""
Orquestador Principal del Pipeline de Transcripción.
Este módulo coordina todo el flujo de trabajo:
    1. Descarga de archivos desde Drive
    2. Routing inteligente (decide qué motor usar)
    3. Normalización condicional de audio
    4. Transcripción (completa o por fragmentos entrelazados en paralelo)
    5. Consolidación de fragmentos con Gemini Flash (si aplica)
    6. Escritura en Google Docs
    7. Callbacks a Google Sheets
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

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
from src.storage.audio_normalizer_service import normalize_and_upload_gcs, split_audio_with_overlap
from src.storage.gcs_cleaner import delete_gcs_files

# Servicios de Transcripción
from src.transcription.transcribers import transcribe_from_gcs_uri as transcribe_stt_v1
from src.transcription.vertex_service import (
    transcribe_with_gemini,
    transcribe_fragment_with_gemini,
)
from src.docs.google_docs_service import append_formatted_transcript
from src.sheets.sheets_service import update_row_status, update_transcription_result
from src.ingestion.auth_service import get_oauth2_credentials

# Métricas
from src.metrics import (
    TRANSCRIPTIONS_TOTAL,
    TRANSCRIPTIONS_ERRORS_TOTAL,
    PIPELINE_DURATION_SECONDS,
    STT_PHASE_SECONDS,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constantes de segmentación
# ---------------------------------------------------------------------------
SEGMENT_MIN: int = 15          # Duración de cada fragmento en minutos
OVERLAP_SEC: int = 90          # Solapamiento entre fragmentos en segundos
MAX_PARALLEL_FRAGMENTS: int = 4  # Máx. llamadas simultáneas a Gemini


# ==============================================================================
# Excepciones
# ==============================================================================

class PipelineError(Exception):
    """Error personalizado del pipeline con código de error"""
    def __init__(self, message: str, code: str = "INTERNAL"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# ==============================================================================
# Utilidades privadas
# ==============================================================================

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
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            parts = line.split(":", 1)
            speaker_info = parts[0].strip()
            content = parts[1].strip()
            formatted_blocks.append(f"{speaker_info}:|SEPARATOR|{content}")
        else:
            formatted_blocks.append(line)
    return "\n\n".join(formatted_blocks)


def _guess_mime_type(gcs_uri: str) -> str:
    """Adivina el tipo MIME basado en la extensión para Vertex AI."""
    mime, _ = mimetypes.guess_type(gcs_uri)
    if not mime:
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
        return "audio/mpeg"
    return mime


def _format_engine_name(engine: str) -> str:
    """Formatea el nombre del motor para visualización"""
    engine_names = {
        "stt_v1": "STT V1 Stereo",
        "gemini_flash": settings.gemini_vertex,
        "gemini_pro": settings.gemini_vertex,
    }
    return engine_names.get(engine, engine)


def _get_local_audio_duration(local_path: str) -> Optional[float]:
    """
    Usa ffprobe para obtener la duración en segundos de un archivo local.
    Devuelve None si ffprobe no está disponible o falla.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                local_path,
            ],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"⚠️ No se pudo determinar duración con ffprobe: {e}")
        return None


def _download_gcs_to_tmp(gcs_uri: str, tmp_dir: str) -> str:
    """
    Descarga un blob de GCS a un directorio temporal local.
    Devuelve la ruta local del archivo descargado.
    """
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name, blob_name = parts[0], parts[1]
    ext = Path(blob_name).suffix or ".mp3"
    local_path = os.path.join(tmp_dir, f"audio_raw{ext}")
    client = storage.Client()
    client.bucket(bucket_name).blob(blob_name).download_to_filename(local_path)
    logger.info(f"📥 Descargado a local: {local_path}")
    return local_path


def _upload_fragment_to_gcs(
    local_path: str,
    case_id: str,
    bucket_name: str,
    fragment_id: str,
) -> str:
    """Sube un fragmento local a GCS y devuelve su URI gs://"""
    fname = Path(local_path).name
    blob_name = f"fragments/{case_id}/{fragment_id}_{fname}"
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    uri = f"gs://{bucket_name}/{blob_name}"
    logger.info(f"☁️ Fragmento {fragment_id} subido: {uri}")
    return uri


# ==============================================================================
# Consolidación de fragmentos — el "pegamento"
# ==============================================================================

def consolidate_fragments(
    fragments_jsonl: List[dict],
    model_name: str = settings.gemini_vertex,
) -> str:
    """
    Envía todos los JSON de fragmentos a Gemini Flash para que:
      1. Elimine las repeticiones exactas en los solapamientos de 90 s.
      2. Unifique los hablantes entre fragmentos (SPEAKER_1_P01 = SPEAKER_1_P02 → un nombre real).
      3. Devuelva el texto final listo para Google Docs.

    Args:
        fragments_jsonl: Lista de dicts, uno por fragmento, con la estructura
                         {"part": "P01", "data": [{"start": ..., "spk": ..., "text": ...}]}.
        model_name:      Modelo Gemini a usar.

    Returns:
        Texto plano consolidado listo para escribir en Google Docs.
    """
    from google import genai
    from google.genai import types

    if not fragments_jsonl:
        raise PipelineError("No hay fragmentos para consolidar.", code="NO_FRAGMENTS")

    # Serializar todos los fragmentos como JSONL (un JSON por línea)
    jsonl_payload = "\n".join(json.dumps(f, ensure_ascii=False) for f in fragments_jsonl)

    consolidation_prompt = f"""Eres un ensamblador de transcripciones. Recibirás varios JSON de transcripción \
que tienen {OVERLAP_SEC} segundos de solapamiento entre el final de uno y el inicio del siguiente.

FRAGMENTOS (formato JSONL — un JSON por línea):
{jsonl_payload}

TU TAREA:
1. Une los textos eliminando la repetición exacta en los solapamientos.
2. Unifica a los hablantes: si SPEAKER_1_P01 y SPEAKER_1_P02 dicen lo mismo en el solape, \
son la misma persona — cámbialos a un nombre unificado (ej: "Hablante 1").
3. Conserva las marcas de tiempo [MM:SS] al inicio de cada turno.
4. Devuelve ÚNICAMENTE el texto final listo para Google Docs, sin JSON, sin explicaciones.

FORMATO DE SALIDA:
[MM:SS] Hablante X: Texto del turno...
[MM:SS] Hablante Y: Texto del turno...
"""

    logger.info(
        f"🔗 Consolidando {len(fragments_jsonl)} fragmento(s) con Gemini Flash..."
    )

    try:
        creds = get_oauth2_credentials()
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
            credentials=creds,
            http_options={"api_version": "v1"},
        )

        generate_config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=16384,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_ONLY_HIGH",
                ),
            ],
        )

        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=consolidation_prompt)],
                )
            ],
            config=generate_config,
        )

        # Extraer texto de forma robusta
        consolidated = ""
        if response.text:
            consolidated = response.text
        else:
            try:
                parts = response.candidates[0].content.parts
                consolidated = "".join(
                    p.text for p in parts if hasattr(p, "text") and p.text
                )
            except (IndexError, AttributeError):
                pass

        if not consolidated.strip():
            raise PipelineError("Gemini devolvió una consolidación vacía.", code="CONSOLIDATION_FAILED")

        logger.info(f"✅ Consolidación completada ({len(consolidated)} chars)")
        return consolidated

    except PipelineError:
        raise
    except Exception as e:
        logger.error(f"❌ Error en consolidación: {e}")
        raise


# ==============================================================================
# Pipeline de segmentación
# ==============================================================================

def _run_segmented_pipeline(
    gcs_input_uri: str,
    case_id: str,
    bucket_name: str,
    mime_type: str,
    model_name: str,
) -> str:
    """
    Ejecuta el pipeline de fragmentos entrelazados:
      1. Descarga el audio GCS → local.
      2. Divide con split_audio_with_overlap (ffmpeg -c copy).
      3. Sube cada fragmento a GCS.
      4. Transcribe todos los fragmentos en paralelo con Gemini Flash.
      5. Consolida la lista de JSONs en texto final.

    Returns:
        Texto consolidado listo para Google Docs.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # --- 1. Descargar audio raw a disco local ---
        logger.info("⬇️ Descargando audio a temporal local para segmentar...")
        local_audio = _download_gcs_to_tmp(gcs_input_uri, tmp_dir)

        # --- 2. Segmentar con ffmpeg (sin recodificar) ---
        logger.info(
            f"✂️ Segmentando en fragmentos de {SEGMENT_MIN} min "
            f"con {OVERLAP_SEC}s de solapamiento..."
        )
        fragment_paths = split_audio_with_overlap(
            local_audio,
            segment_min=SEGMENT_MIN,
            overlap_sec=OVERLAP_SEC,
        )
        logger.info(f"📦 {len(fragment_paths)} fragmento(s) generado(s).")

        # --- 3. Subir fragmentos a GCS ---
        fragment_gcs_uris: List[Dict[str, str]] = []
        for idx, fpath in enumerate(fragment_paths, start=1):
            fragment_id = f"P{idx:02d}"
            uri = _upload_fragment_to_gcs(fpath, case_id, bucket_name, fragment_id)
            fragment_gcs_uris.append({"fragment_id": fragment_id, "uri": uri})

    # --- 4. Transcripción paralela ---
    logger.info(
        f"🚀 Transcribiendo {len(fragment_gcs_uris)} fragmento(s) "
        f"en paralelo (max {MAX_PARALLEL_FRAGMENTS} workers)..."
    )
    fragments_jsonl: List[dict] = [None] * len(fragment_gcs_uris)  # type: ignore

    def _transcribe_one(item: Dict[str, str], position: int) -> tuple[int, dict]:
        frag_id = item["fragment_id"]
        uri = item["uri"]
        result = transcribe_fragment_with_gemini(
            gcs_uri=uri,
            fragment_id=frag_id,
            model_name=model_name,
            mime_type=mime_type,
        )
        return position, result

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FRAGMENTS) as executor:
        futures = {
            executor.submit(_transcribe_one, item, idx): idx
            for idx, item in enumerate(fragment_gcs_uris)
        }
        for future in as_completed(futures):
            try:
                pos, result = future.result()
                fragments_jsonl[pos] = result
                logger.info(f"✅ Fragmento {result.get('part')} transcrito.")
            except Exception as exc:
                orig_idx = futures[future]
                frag_id = fragment_gcs_uris[orig_idx]["fragment_id"]
                logger.error(f"❌ Error transcribiendo {frag_id}: {exc}")
                # Insertar fragmento vacío para no bloquear la consolidación
                fragments_jsonl[orig_idx] = {"part": frag_id, "data": [], "error": str(exc)}

    # Filtrar posibles None residuales
    fragments_jsonl = [f for f in fragments_jsonl if f is not None]

    # --- 5. Consolidar ---
    consolidated_text = consolidate_fragments(fragments_jsonl, model_name=model_name)
    return consolidated_text


# ==============================================================================
# ORQUESTADOR PRINCIPAL
# ==============================================================================

def run_transcription_pipeline(request: TranscriptionRequest) -> Dict[str, Any]:
    """
    Orquesta todo el proceso de transcripción con routing inteligente.

    Flujo:
    1. Descarga archivo de Drive → GCS (raw)
    2. Detección de duración del audio
    3. Router decide estrategia (siempre Gemini Flash; activa segmentación si > 20 min)
    4. Normalización condicional (solo si es necesario)
    5a. Transcripción directa (audio corto)
    5b. Pipeline de fragmentos entrelazados (audio largo → segmentar → paralelo → consolidar)
    6. Escritura en Google Docs
    7. Callbacks a Google Sheets
    8. Limpieza de archivos temporales

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

        logger.info("📥 [1/6] Descargando archivo de Drive...")
        gcs_raw_uri = save_drive_audio_to_gcs(drive_link, request.case_id)
        uris_creados.append(gcs_raw_uri)
        logger.info(f"✅ Archivo en GCS: {gcs_raw_uri}")

        # ---------------------------------------------------------
        # PASO 2: Detección de duración (para routing de segmentación)
        # ---------------------------------------------------------
        logger.info("⏱️ [2/6] Detectando duración del audio...")
        audio_duration: Optional[float] = None
        try:
            with tempfile.TemporaryDirectory() as probe_dir:
                local_for_probe = _download_gcs_to_tmp(gcs_raw_uri, probe_dir)
                audio_duration = _get_local_audio_duration(local_for_probe)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo detectar duración: {e}. Se usará transcripción directa.")

        if audio_duration:
            logger.info(f"🕐 Duración detectada: {audio_duration:.1f}s ({audio_duration/60:.1f} min)")
        else:
            logger.info("🕐 Duración desconocida — se usará transcripción directa.")

        # ---------------------------------------------------------
        # PASO 3: Router Inteligente
        # ---------------------------------------------------------
        logger.info("🧠 [3/6] Ejecutando router inteligente...")
        if request.strategy != "auto":
            logger.info(f"⚙️ Estrategia manual sobrescrita: {request.strategy}")
            from src.orchestration.router import RoutingDecision
            decision = RoutingDecision(
                engine="gemini_flash",
                requires_normalization=False,
                target_channels=1,
                reason=f"Estrategia manual: {request.strategy} → forzado a gemini_flash",
                requires_segmentation=False,
                duration_seconds=audio_duration,
            )
        else:
            decision = decide_transcription_strategy(
                request, gcs_raw_uri, duration_seconds=audio_duration
            )

        logger.info(
            f"✅ Motor: {_format_engine_name(decision.engine)} | "
            f"Segmentación: {'SÍ 🔪' if decision.requires_segmentation else 'NO'}"
        )

        # ---------------------------------------------------------
        # PASO 4: Normalización
        # ---------------------------------------------------------
        logger.info("🎛️ [4/6] Evaluando necesidad de normalización...")
        gcs_input_uri = gcs_raw_uri

        if decision.requires_normalization:
            logger.info(f"🔧 Normalizando audio (canales: {decision.target_channels})...")
            if should_normalize_audio(decision, gcs_raw_uri):
                gcs_input_uri = normalize_and_upload_gcs(
                    gcs_raw_uri, request.case_id,
                    bucket_name=request.bucket_name or settings.gcs_bucket,
                    target_format="mp3", target_channels=1,
                    auto_sr=False, force_normalize=False,
                )
            if gcs_input_uri != gcs_raw_uri:
                uris_creados.append(gcs_input_uri)
                logger.info(f"✅ Audio normalizado: {gcs_input_uri}")
        else:
            logger.info("⚡ Bypass de normalización — usando archivo raw")

        # ---------------------------------------------------------
        # PASO 5: Transcripción
        # ---------------------------------------------------------
        logger.info(f"📝 [5/6] Transcribiendo con {_format_engine_name(decision.engine)}...")
        stt_start = time.time()
        transcription_text = ""
        model_name = settings.gemini_vertex
        mime_type = _guess_mime_type(gcs_input_uri)
        bucket_name = request.bucket_name or settings.gcs_bucket

        if decision.requires_segmentation:
            # ── Pipeline de fragmentos entrelazados ──────────────────────────
            logger.info(
                f"🔪 Iniciando pipeline de segmentación "
                f"({SEGMENT_MIN} min / {OVERLAP_SEC}s solape)..."
            )
            raw_text = _run_segmented_pipeline(
                gcs_input_uri=gcs_input_uri,
                case_id=request.case_id,
                bucket_name=bucket_name,
                mime_type=mime_type,
                model_name=model_name,
            )
            transcription_text = _parse_gemini_output(raw_text)

        else:
            # ── Transcripción directa (audio corto) ──────────────────────────
            logger.info(f"📤 Enviando a Gemini directo (mime: {mime_type})")
            raw_gemini_text = transcribe_with_gemini(
                gcs_input_uri,
                model_name=model_name,
                mime_type=mime_type,
                language_code=request.language_code,
            )
            transcription_text = _parse_gemini_output(raw_gemini_text)

        stt_duration = time.time() - stt_start
        STT_PHASE_SECONDS.labels(backend=decision.engine).observe(stt_duration)

        if not transcription_text.strip():
            raise PipelineError("La transcripción resultó vacía.", code="STT_FAILED")

        # Guardar respaldo TXT en GCS
        try:
            _, key = gcs_input_uri.replace("gs://", "").split("/", 1)
            stem = PurePosixPath(key).stem
            suffix = "segmented" if decision.requires_segmentation else decision.engine
            txt_blob_path = f"transcripts/{request.case_id}/{stem}_{suffix}.txt"
            bucket = storage_client.bucket(bucket_name)
            bucket.blob(txt_blob_path).upload_from_string(
                transcription_text, content_type="text/plain"
            )
            logger.info(f"💾 Respaldo TXT: gs://{bucket.name}/{txt_blob_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo guardar respaldo TXT: {e}")

        # ---------------------------------------------------------
        # PASO 6: Google Docs + Sheets
        # ---------------------------------------------------------
        logger.info("📄 [6/6] Escribiendo en Google Docs...")
        append_formatted_transcript(
            doc_id=request.doc_id,
            title=request.title,
            transcript_text=transcription_text,
        )
        doc_url = f"https://docs.google.com/document/d/{request.doc_id}/edit"
        logger.info(f"✅ Doc actualizado: {doc_url}")

        if request.sheet_callback:
            logger.info("📊 Actualizando Google Sheets...")
            cb = request.sheet_callback
            update_data = {
                "doc_url": doc_url,
                "status": "✅ Transcrito",
                "engine": _format_engine_name(decision.engine),
                "duration_seconds": time.time() - start_time,
                "transcript_doc_col": cb.transcript_doc_col,
                "status_col": cb.status_col,
            }
            try:
                update_transcription_result(
                    cb.spreadsheet_id, cb.sheet_name, cb.row_index, update_data
                )
            except Exception as e:
                logger.error(f"❌ Error actualizando Sheets: {e}")

        # Limpieza
        logger.info("🧹 Limpiando archivos temporales en GCS...")
        delete_gcs_files(uris_creados)

        # Métricas
        total_duration = time.time() - start_time
        PIPELINE_DURATION_SECONDS.observe(total_duration)
        TRANSCRIPTIONS_TOTAL.labels(backend=decision.engine).inc()

        # ---------------------------------------------------------
        # Generic Chaining (siguiente servicio)
        # ---------------------------------------------------------
        if request.next_step_task:
            next_step = request.next_step_task
            logger.info(f"🔄 Encolando siguiente paso: {next_step.target_service_name}")
            next_payload = next_step.payload_template.copy()
            next_payload.update(
                {
                    "transcription_doc_id": request.doc_id,
                    "transcription_doc_url": doc_url,
                    "case_id": request.case_id,
                    "source_file_id": request.drive_file_id,
                    "status": "transcription_completed",
                }
            )
            enqueuer_payload = {
                "service": next_step.target_service_name,
                "payload": next_payload,
            }
            try:
                resp = requests.post(
                    str(next_step.enqueuer_url),
                    json=enqueuer_payload,
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"✅ Tarea '{next_step.target_service_name}' encolada.")
            except Exception as e:
                logger.error(f"❌ Error al encolar siguiente paso: {e}")

        logger.info(f"🎉 Pipeline completado en {total_duration:.1f}s")

        return {
            "case_id": request.case_id,
            "doc_id": request.doc_id,
            "doc_url": doc_url,
            "status": "success",
            "backend_display_name": _format_engine_name(decision.engine),
            "backend_used": decision.engine,
            "segmented": decision.requires_segmentation,
            "duration_seconds": total_duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error en Pipeline: {e}", exc_info=True)
        TRANSCRIPTIONS_ERRORS_TOTAL.labels(code=getattr(e, "code", "INTERNAL")).inc()
        if request.sheet_callback and request.sheet_callback.status_col:
            try:
                cb = request.sheet_callback
                update_row_status(
                    cb.spreadsheet_id,
                    cb.sheet_name,
                    cb.row_index,
                    cb.status_col,
                    f"❌ Error: {str(e)[:100]}",
                )
            except Exception:
                pass
        raise e