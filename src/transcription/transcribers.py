#src/transcription/transcribers.py
from __future__ import annotations
import os
import time
from typing import Optional, List, Dict, Any

from google.cloud import speech_v1 as speech
from google.api_core.exceptions import GoogleAPICallError

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger(__name__)

# ================================================================
# 1. UTILIDADES Y FORMATO
# ================================================================

def _seconds_to_time_str(total_seconds: float) -> str:
    """Convierte segundos (float) a formato MM:SS."""
    seconds = int(total_seconds)
    m = seconds // 60
    s = seconds % 60
    return f"{m:02}:{s:02}"

def _setup_credentials():
    """Asegura que las credenciales estén en el entorno."""
    if settings.google_application_credentials:
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
             if os.path.exists(settings.google_application_credentials):
                 os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

# ================================================================
# 2. PARSER DE ESTÉREO (INTERCALADO CRONOLÓGICO)
# ================================================================

def _parse_stereo_response(response: speech.LongRunningRecognizeResponse) -> str:
    """
    Procesa la respuesta de V1 en modo 'separate_recognition_per_channel'.
    Toma las palabras de ambos canales, las ordena por tiempo y genera el formato de bloque.
    """
    # 1. Recopilar todas las palabras con su canal y tiempo
    all_words: List[Dict[str, Any]] = []

    # Iteramos sobre los resultados. En modo estéreo, Google devuelve resultados
    # etiquetados con channel_tag (1=Izquierdo/Agente, 2=Derecho/Cliente).
    for result in response.results:
        # channel_tag viene a nivel de resultado
        channel = result.channel_tag
        
        # Fallback: Si channel es 0, asumimos 1
        if channel == 0: 
            channel = 1
            
        # Tomamos la mejor alternativa
        if not result.alternatives:
            continue
            
        alternative = result.alternatives[0]
        
        # Necesitamos palabras con tiempos para ordenar
        for word_info in alternative.words:
            all_words.append({
                "word": word_info.word,
                "start_time": word_info.start_time.total_seconds(),
                "channel": channel
            })

    if not all_words:
        return "⚠️ Audio procesado pero no se detectaron palabras (posible silencio o error de formato)."

    # 2. Ordenar cronológicamente para mezclar la conversación
    # Esto es vital: mezcla las dos pistas en una sola línea de tiempo
    all_words.sort(key=lambda x: x["start_time"])

    # 3. Construir bloques de texto por turno de hablante
    output_blocks = []
    
    current_channel = None
    current_buffer = []
    block_start_time = 0.0

    for item in all_words:
        ch = item["channel"]
        word = item["word"]
        time = item["start_time"]

        # Si cambiamos de canal (hablante), cerramos el bloque anterior
        if current_channel is not None and ch != current_channel:
            timestamp = _seconds_to_time_str(block_start_time)
            text_block = " ".join(current_buffer)
            
            # Mapeo de canales a etiquetas legibles
            # Canal 1 suele ser Izquierdo (Agente 8x8), Canal 2 Derecho (Cliente)
            speaker_label = "Agente" if current_channel == 1 else "Cliente"
            
            # Formato requerido por tu sistema
            block_str = f"[{timestamp}] {speaker_label}:|SEPARATOR|{text_block}"
            output_blocks.append(block_str)
            
            # Reiniciar buffer
            current_buffer = []
            block_start_time = time # El nuevo bloque empieza con esta palabra
        
        if current_buffer == []:
            block_start_time = time
            
        current_channel = ch
        current_buffer.append(word)

    # 4. Agregar el último bloque pendiente
    if current_channel and current_buffer:
        timestamp = _seconds_to_time_str(block_start_time)
        text_block = " ".join(current_buffer)
        speaker_label = "Agente" if current_channel == 1 else "Cliente"
        
        block_str = f"[{timestamp}] {speaker_label}:|SEPARATOR|{text_block}"
        output_blocks.append(block_str)

    return "\n\n".join(output_blocks)

# ================================================================
# 3. MOTOR DE TRANSCRIPCIÓN (V1 TRUE STEREO)
# ================================================================

def transcribe_from_gcs_uri(
    gcs_wav_uri: str,
    *,
    language_code: Optional[str] = None,
) -> str:
    """
    Transcribe usando Google Speech-to-Text V1 optimizado para llamadas ESTÉREO (8x8).
    
    Estrategia: 'True Stereo'
    - No usa diarización por IA.
    - Separa físicamente el canal izquierdo (Agente) del derecho (Cliente).
    - Ordena las palabras por timestamp para reconstruir el diálogo.
    """
    _setup_credentials()

    client = speech.SpeechClient()
    
    logger.info(f"🎙️ [STT V1 Stereo] Iniciando transcripción: {gcs_wav_uri}")

    audio = speech.RecognitionAudio(uri=gcs_wav_uri)

    # CONFIGURACIÓN OPTIMIZADA PARA 8x8 STEREO
    # Nota: Asumimos que el audio ya fue validado como Estéreo en el paso anterior.
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
        sample_rate_hertz=8000,
        language_code=language_code or settings.stt_language_code,
        
        # --- CONFIGURACIÓN DE CANALES (EL SECRETO) ---
        audio_channel_count=2, 
        enable_separate_recognition_per_channel=True,
        
        # --- IMPORTANTE: TIMESTAMPS ---
        # Necesarios para ordenar las frases del canal 1 y 2 cronológicamente
        enable_word_time_offsets=True,
        
        enable_automatic_punctuation=True,
        model="phone_call", # El mejor modelo para telefonía
        use_enhanced=True,
    )

# ... dentro de transcribe_from_gcs_uri ...

    try:
        logger.info("⏳ Enviando operación LongRunning (V1)...")
        operation = client.long_running_recognize(config=config, audio=audio)
        
        # --- CAMBIO: BUCLE DE POLLING MANUAL (Anti-Timeout) ---
        # En lugar de bloquearnos por 3 horas en silencio, preguntamos cada 10s.
        # Esto evita que balanceadores de carga o firewalls corten la conexión por inactividad.
        
        start_time = time.time()
        max_seconds = 11000  # 3 horas aprox
        
        logger.info(f"🔄 Polling iniciado. ID Operación: {operation.operation.name}")
        
        while not operation.done():
            # Verificar si excedimos el tiempo total
            elapsed = time.time() - start_time
            if elapsed > max_seconds:
                raise TimeoutError(f"La transcripción excedió el límite de {max_seconds}s.")
            
            # Log de latidos cada ~60 segundos para que veas que sigue vivo
            if int(elapsed) % 60 == 0:
                logger.info(f"   ... procesando STT ({int(elapsed)}s transcurridos) ...")
            
            # Esperar 10 segundos antes de volver a preguntar
            time.sleep(10)

        # Una vez que done() es True, result() devuelve la respuesta inmediatamente
        response = operation.result()
        # -------------------------------------------------------
        
        logger.info("✅ Transcripción V1 finalizada exitosamente.")
        
        # Parsear resultado
        full_text = _parse_stereo_response(response)
        return full_text

    except GoogleAPICallError as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Error crítico en transcripción: {e}")
        raise e