from __future__ import annotations
from typing import Optional, List
import os
import tempfile

from google.api_core import exceptions as gexc
from google.cloud import speech_v2
from google.cloud.speech_v2.types import CreateRecognizerRequest, Recognizer

from src.logging_conf import get_logger
from src.settings import get_settings

logger = get_logger(__name__)

# ================================================================
# SPEECH V2 HELPERS
# ================================================================

def _speech_client(location: str = "global") -> speech_v2.SpeechClient:
    """Devuelve un SpeechClient apuntando explícitamente al endpoint de la location."""
    api_endpoint = (
        "speech.googleapis.com" if location == "global" else f"{location}-speech.googleapis.com"
    )
    return speech_v2.SpeechClient(client_options={"api_endpoint": api_endpoint})


def _recognizer_path(project_id: Optional[str], location: str, recognizer_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/recognizers/{recognizer_id}"


def _ensure_recognizer(
    *,
    project_id: Optional[str],
    location: str = "global",
    recognizer_id: str = "default-stt",
    language_code: str = "es-MX",
    model: str = "long",
    enable_diarization: bool = False,
) -> Optional[str]:
    """Obtiene o crea un Recognizer v2 y devuelve su 'name'."""
    client = _speech_client(location)
    parent = f"projects/{project_id}/locations/{location}"
    name = _recognizer_path(project_id, location, recognizer_id)

    try:
        client.get_recognizer(name=name)
        logger.info("Recognizer existente: %s", name)
        return name
    except gexc.NotFound:
        pass

    rec = Recognizer(
        display_name="Default STT (auto)",
        default_recognition_config=speech_v2.RecognitionConfig(
            auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
            language_codes=[language_code],
            model=model,
            features=speech_v2.RecognitionFeatures(
                enable_automatic_punctuation=True,
                diarization_config=(
                    speech_v2.SpeakerDiarizationConfig(
                        min_speaker_count=2, max_speaker_count=2
                    ) if enable_diarization else None
                ),
            ),
        ),
    )

    req = CreateRecognizerRequest(parent=parent, recognizer_id=recognizer_id, recognizer=rec)
    logger.info("Creando Recognizer en %s con id '%s'…", parent, recognizer_id)
    op = client.create_recognizer(request=req)
    created: Optional[Recognizer] = op.result(timeout=600)
    if created:
        logger.info("Recognizer creado: %s", created.name)
        return created.name
    logger.error("No se pudo crear Recognizer.")
    return None



# ================================================================
# GEMINI VIA AI STUDIO (API KEY)
# ================================================================

def gemini_transcribe_gcs(
    gcs_wav_uri: str,
    *,
    model_name: str = "gemini-2.0-flash",
    prompt: Optional[str] = None,
    mime_type: str = "audio/wav",
    language_code: Optional[str] = None,
) -> str:
    """Transcribe un archivo desde GCS usando Google Generative AI (API key)."""
    import google.generativeai as genai
    from google.cloud import storage

    s = get_settings()
    if not s.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en settings/env para usar Gemini.")

    genai.configure(api_key=s.gemini_api_key)
    model = genai.GenerativeModel(model_name=model_name, generation_config={"temperature": 0.0})

    # Prompt con pista de idioma
    lang = language_code or getattr(s, "stt_language_code", None) or "es-ES"
    base_prompt = (
        prompt
        or getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
        or "Transcribe fielmente el audio (sin parafrasear)."
    )
    system_prompt = f"{base_prompt}\n\nIdioma objetivo: {lang}. No traduzcas; conserva el idioma original del audio."

    if not gcs_wav_uri.startswith("gs://"):
        raise ValueError(f"URI inválida: {gcs_wav_uri}")

    bucket_name, blob_name = gcs_wav_uri.replace("gs://", "").split("/", 1)
    tmp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(tmp_path)
    logger.info("📥 Archivo descargado temporalmente desde GCS: %s", tmp_path)

    uploaded = genai.upload_file(tmp_path, mime_type=mime_type)
    logger.info("📤 Archivo subido a AI Studio: %s", uploaded.name)

    resp = model.generate_content(
        [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "user", "parts": [uploaded]},
        ]
    )
    text = (getattr(resp, "text", "") or "").strip()

    try:
        os.remove(tmp_path)
        logger.info("🧹 Archivo temporal eliminado: %s", tmp_path)
    except Exception as e:
        logger.warning("No se pudo eliminar el archivo temporal: %s", e)

    return text

# ================================================================
# GEMINI VIA VERTEX AI (SERVICE ACCOUNT)
# ================================================================

def gemini_vertex_transcribe_gcs(
    gcs_wav_uri: str,
    *,
    model_name: str = "gemini-2.0-flash",
    mime_type: str = "audio/wav",
    system_prompt: str | None = None,
    language_code: Optional[str] = None,
) -> str:
    """Transcribe un archivo de audio directamente desde GCS usando Vertex AI Gemini."""
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part

    s = get_settings()
    project_id = getattr(s, "gcp_project_id", None) or s.project_id
    region = getattr(s, "gcp_region", None) or getattr(s, "vertex_location", None)

    if not project_id or not region:
        raise ValueError("Faltan variables GCP_PROJECT_ID o GCP_REGION en .env")

    vertexai.init(project=project_id, location=region)

    lang = language_code or getattr(s, "stt_language_code", None) or "es-ES"
    base_prompt = system_prompt or getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None)
    if not base_prompt:
        base_prompt = (
            "Transcribe fielmente el audio (sin parafrasear). "
            "Usa puntuación básica y marca lo inaudible como [Nota: inaudible]."
        )
    prompt_text = f"{base_prompt}\n\nIdioma objetivo: {lang}. No traduzcas; conserva el idioma original del audio."

    logger.info("🧠 Prompt (%d chars): %.200s...", len(prompt_text), prompt_text)

    model = GenerativeModel(model_name)
    audio_part = Part.from_uri(gcs_wav_uri, mime_type=mime_type)

    resp = model.generate_content([prompt_text, audio_part])
    text = (getattr(resp, "text", "") or "").strip()
    logger.info("✅ Transcripción obtenida (%d caracteres)", len(text))
    return text


# ================================================================
# SPEECH-TO-TEXT V2
# ================================================================

def stt_v2_transcribe_gcs(
    gcs_wav_uri: str,
    *,
    language: str | None = None,
    language_code: str | None = None,
    diarization: bool | None = None,
    model: str = "long",
    automatic_punctuation: bool = True,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> str:
    """Reconocimiento síncrono con alias language_code."""
    s = get_settings()
    lang = language_code or language or s.stt_language_code or "es-MX"
    diarization = bool(s.stt_enable_diarization if diarization is None else diarization)
    min_speakers = min_speakers or int(os.getenv("STT_MIN_SPEAKERS", "2"))
    max_speakers = max_speakers or int(os.getenv("STT_MAX_SPEAKERS", "2"))
    location = (getattr(s, "speech_location", None) or os.getenv("SPEECH_LOCATION", "global")).lower()

    client = _speech_client(location)
    recognizer = (
        getattr(s, "speech_recognizer", None)
        or os.getenv("SPEECH_RECOGNIZER", "").strip()
    )
    if not recognizer:
        recognizer = _ensure_recognizer(
            project_id=s.project_id,
            location=location,
            recognizer_id="default-stt",
            language_code=lang,
            model=model,
            enable_diarization=False,
        )

    logger.info(
        "STT v2 | endpoint=%s | recognizer=%s | lang=%s | diarization=%s",
        location, recognizer, lang, diarization,
    )

    feats = speech_v2.RecognitionFeatures(
        enable_automatic_punctuation=automatic_punctuation,
        diarization_config=(
            speech_v2.SpeakerDiarizationConfig(
                min_speaker_count=min_speakers,
                max_speaker_count=max_speakers,
            ) if diarization else None
        ),
    )

    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
        language_codes=[lang],
        model=model,
        features=feats,
    )

    try:
        resp = client.recognize(
            request=speech_v2.RecognizeRequest(
                recognizer=recognizer,
                config=config,
                uri=gcs_wav_uri,
            )
        )
    except gexc.NotFound:
        logger.warning("Recognizer no encontrado. Reintentando con nuevo recognizer…")
        recognizer = _ensure_recognizer(
            project_id=s.project_id,
            location=location,
            recognizer_id="default-stt",
            language_code=lang,
            model=model,
        )
        resp = client.recognize(
            request=speech_v2.RecognizeRequest(
                recognizer=recognizer,
                config=config,
                uri=gcs_wav_uri,
            )
        )

    parts: List[str] = []
    for result in resp.results:
        if result.alternatives:
            parts.append(result.alternatives[0].transcript.strip())

    return "\n".join(p for p in parts if p).strip()


# ================================================================
# FACADE PRINCIPAL
# ================================================================

def transcribe_from_gcs_uri(
    gcs_wav_uri: str,
    *,
    language_code: Optional[str] = None,
    prompt: Optional[str] = None,
) -> str:
    """Selecciona el backend configurado y ejecuta la transcripción (con language_code)."""
    s = get_settings()
    backend = (s.transcriber or "stt_v2").lower()
    lang = language_code or getattr(s, "stt_language_code", None) or "es-MX"

    if backend == "gemini_vertex":
        return gemini_vertex_transcribe_gcs(
            gcs_wav_uri,
            system_prompt=prompt or getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None),
            language_code=lang,
        )

    if backend == "gemini":
        return gemini_transcribe_gcs(
            gcs_wav_uri,
            prompt=prompt or getattr(s, "TRANSCRIPTION_PROMPT_TEMPLATE", None),
            language_code=lang,
        )

    return stt_v2_transcribe_gcs(
        gcs_wav_uri,
        language_code=lang,
        diarization=s.stt_enable_diarization,
    )

def stt_v2_transcribe_gcs_lro(
    gcs_wav_uri: str,
    *,
    language: str | None = None,
    language_code: str | None = None,
    diarization: bool | None = None,
    model: str = "long",
    automatic_punctuation: bool = True,
    timeout_sec: int = 3600,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> str:
    """BatchRecognize para audios largos (LRO) con alias language_code."""
    from google.cloud import speech_v2
    from google.api_core import exceptions as gexc

    s = get_settings()
    lang = language_code or language or s.stt_language_code or "es-MX"
    diarization = bool(s.stt_enable_diarization if diarization is None else diarization)
    min_speakers = min_speakers or int(os.getenv("STT_MIN_SPEAKERS", "2"))
    max_speakers = max_speakers or int(os.getenv("STT_MAX_SPEAKERS", "2"))
    location = (getattr(s, "speech_location", None) or "global").lower()

    client = _speech_client(location)
    recognizer = _ensure_recognizer(
        project_id=s.project_id,
        location=location,
        recognizer_id="default-stt",
        language_code=lang,
        model=model,
    )

    feats = speech_v2.RecognitionFeatures(
        enable_automatic_punctuation=automatic_punctuation,
        diarization_config=(
            speech_v2.SpeakerDiarizationConfig(
                min_speaker_count=min_speakers,
                max_speaker_count=max_speakers,
            ) if diarization else None
        ),
    )

    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
        language_codes=[lang],
        model=model,
        features=feats,
    )

    req = speech_v2.BatchRecognizeRequest(
        recognizer=recognizer,
        config=config,
        files=[speech_v2.BatchRecognizeFileMetadata(uri=gcs_wav_uri)],
        recognition_output_config=speech_v2.RecognitionOutputConfig(
            inline_response_config=speech_v2.InlineOutputConfig()
        ),
    )

    logger.info("🎧 Ejecutando BatchRecognize (LRO) en archivo grande: %s", gcs_wav_uri)
    op = client.batch_recognize(request=req)
    response = op.result(timeout=timeout_sec)

    parts: list[str] = []
    if response:
        for result in response.results:
            if result.alternatives:
                parts.append(result.alternatives[0].transcript.strip())

        text = "\n".join(p for p in parts if p).strip()
        logger.info("✅ LRO completado (%d caracteres)", len(text))
        return text
    else:
        logger.info("result esta vacio")
        return ""
