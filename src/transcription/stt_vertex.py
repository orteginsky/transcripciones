from pathlib import Path

from src.logging_conf import get_logger
from src.settings import GCP_PROJECT_ID, STT_LANGUAGE_CODE

from google.cloud import speech_v2

import os


logger = get_logger(__name__)


def transcribe_wav16k(audio_path: Path) -> str:
    """
    Transcribe un archivo WAV 16 kHz mono usando Speech-to-Text v2.
    Retorna el texto completo.
    """
    client = speech_v2.SpeechClient()

    # Configuración del reconocimiento
    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),  # detecta WAV/PCM
        language_codes=[STT_LANGUAGE_CODE],
        model="latest_long",           # "latest_short" para clips <60s
        features=speech_v2.RecognitionFeatures(
            enable_word_time_offsets=True
        )
    )
    audio_content = Path(audio_path).read_bytes()
    logger.info("Enviando %s a Speech-to-Text v2", audio_path)
    
    request = speech_v2.RecognizeRequest(
        recognizer=f"projects/{GCP_PROJECT_ID}/locations/global/recognizers/_", # Usar '_' es una práctica común para el recognizer por defecto
        config=config,
        content=audio_content, # <-- ¡EL CAMBIO CLAVE ESTÁ AQUÍ!
    )

    response = client.recognize(request=request)

    # Concatenar resultados
    transcript = " ".join(
        [result.alternatives[0].transcript for result in response.results]
    )
    logger.info("Transcripción completada (%d caracteres)", len(transcript))
    return transcript
