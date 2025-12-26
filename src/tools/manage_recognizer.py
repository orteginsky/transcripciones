# src/tools/manage_recognizer.py
from __future__ import annotations

import argparse

from google.api_core.exceptions import NotFound
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

from src.settings import settings
from src.logging_conf import get_logger

logger = get_logger(__name__)

PROJECT_ID = settings.gcp_project_id
LOCATION = settings.speech_location.lower()  # ej. "global"
RECOGNIZER_ID = "default-stt"


def delete_recognizer() -> None:
    client = speech_v2.SpeechClient()
    name = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/{RECOGNIZER_ID}"

    logger.info("🗑️ Eliminando recognizer si existe: %s", name)
    try:
        op = client.delete_recognizer(
            request=cloud_speech.DeleteRecognizerRequest(
                name=name,
                allow_missing=True,  # si no existe, no truena
            )
        )
        # Esperar resultado con manejo de excepciones mejorado
        try:
            op.result(timeout=300)
            logger.info("✅ Delete completado: %s", name)
        except Exception:
            # Si allow_missing=True y no existía, puede dar error en result()
            logger.info("ℹ️ Delete operation completed (recognizer may not have existed): %s", name)
    except NotFound:
        logger.info("ℹ️ Recognizer no encontrado, nada que borrar: %s", name)
    except Exception as e:
        logger.warning("⚠️ Error borrando recognizer (continuando): %s", e)


def create_recognizer_with_diarization() -> str:
    """
    Crea un recognizer básico SIN diarization en la config.

    NOTA: La diarización NO se soporta en el recognizer config de STT v2.
    En su lugar, se debe especificar en cada request individual (ver transcribers.py).
    """
    client = speech_v2.SpeechClient()
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"

    # Recognizer básico sin diarization (no soportado en recognizer config)
    recognizer = cloud_speech.Recognizer(
        default_recognition_config=cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[settings.stt_language_code],
            model="long",
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                # ⛔ NO incluir diarization_config aquí - causa error 400
            ),
        )
    )

    req = cloud_speech.CreateRecognizerRequest(
        parent=parent,
        recognizer_id=RECOGNIZER_ID,
        recognizer=recognizer,
    )

    logger.info("🎛️ Creando recognizer '%s' en %s ...", RECOGNIZER_ID, parent)
    op = client.create_recognizer(request=req)
    created = op.result(timeout=600)
    logger.info("✅ Recognizer creado: %s", created.name)
    print(created.name)
    return created.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["delete", "create", "recreate"])
    args = parser.parse_args()

    if args.action == "delete":
        delete_recognizer()
    elif args.action == "create":
        create_recognizer_with_diarization()
    elif args.action == "recreate":
        delete_recognizer()
        create_recognizer_with_diarization()


if __name__ == "__main__":
    main()
