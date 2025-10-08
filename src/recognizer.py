# src/recognizer.py
from google.cloud import speech_v2
from google.api_core import exceptions
from src.settings import GCP_PROJECT_ID

client = speech_v2.SpeechClient()
parent = f"projects/{GCP_PROJECT_ID}/locations/global"
recognizer_id = "default"
recognizer_name = f"{parent}/recognizers/{recognizer_id}"

# ✅ Aquí añadimos el modelo
recognizer_config = speech_v2.Recognizer(
    language_codes=["es-MX"],
    display_name="default_recognizer_mx",
    model="latest_long",  # <-- obligatorio
)

try:
    operation = client.create_recognizer(
        parent=parent,
        recognizer_id=recognizer_id,
        recognizer=recognizer_config,
    )
    print("Creando recognizer, espera unos segundos...")
    response = operation.result()  # espera a que termine
    print("Recognizer creado exitosamente:", recognizer_name)

except exceptions.AlreadyExists:
    print(f"El recognizer '{recognizer_name}' ya existe. No se realizaron cambios.")
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")
