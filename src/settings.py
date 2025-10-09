# src.settings
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar las variables de .env
load_dotenv()

# --- GCP / Vertex ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# --- Modelos ---
VERTEX_MODEL_PUBLISHER = os.getenv("VERTEX_MODEL_PUBLISHER")
VERTEX_MODEL_NAME = os.getenv("VERTEX_MODEL_NAME")
VERTEX_TEMPERATURE = float(os.getenv("VERTEX_TEMPERATURE", "0.2"))
VERTEX_MAX_TOKENS = int(os.getenv("VERTEX_MAX_TOKENS", "4000"))

# --- Speech-to-Text ---
STT_ENGINE = os.getenv("STT_ENGINE", "google")
STT_LANGUAGE_CODE = os.getenv("STT_LANGUAGE_CODE", "es-MX")
STT_ENABLE_DIARIZATION = os.getenv("STT_ENABLE_DIARIZATION", "false").lower() == "true"

# --- Storage ---
USE_GCS = os.getenv("USE_GCS", "false").lower() == "true"
GCS_BUCKET = os.getenv("GCS_BUCKET")
GCS_BUCKET_OUTPUT = os.getenv("GCS_BUCKET_OUTPUT", GCS_BUCKET)

# --- Rutas locales ---
INPUT_DIR  = Path(os.getenv("INPUT_DIR", "./data/input"))
WORK_DIR   = Path(os.getenv("WORK_DIR", "./data/work"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./data/output"))

# --- PDF ---
PDF_FOOTER_TEXT = os.getenv("PDF_FOOTER_TEXT", "")
PDF_HEADER_TEXT = os.getenv("PDF_HEADER_TEXT", "")

MP3_SOURCE_DIR = Path(os.getenv("MP3_SOURCE_DIR", "./data/mp3"))
WAV_OUTPUT_DIR = Path(os.getenv("WAV_OUTPUT_DIR", "./data/wav16k"))
NORMALIZE_TARGET_DB = float(os.getenv("NORMALIZE_TARGET_DB", "-20"))

# --- Google OAuth (Sheets / Drive) ---
GOOGLE_OAUTH_CREDENTIALS_FILE = Path(
    os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "./credentials.json")
)
GOOGLE_OAUTH_TOKEN_FILE = Path(
    os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "./token.json")
)
# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TRANSCRIPTION_PROMPT_FILE = Path(os.getenv("TRANSCRIPTION_PROMPT_FILE", "./src/domain/prompts/transcription_prompt.md.j2"))

# Leer el contenido del archivo
if TRANSCRIPTION_PROMPT_FILE.exists():
    TRANSCRIPTION_PROMPT_TEMPLATE = TRANSCRIPTION_PROMPT_FILE.read_text(encoding="utf-8")
else:
    TRANSCRIPTION_PROMPT_TEMPLATE = "Transcribe el siguiente audio."  # fallback

SERVICE_ACCOUNT_SANDBOX_FOLDER = Path(os.getenv("SERVICE_ACCOUNT_SANDBOX_FOLDER", "credencial"))


if __name__=="__main__":
    print(TRANSCRIPTION_PROMPT_FILE)
    print(TRANSCRIPTION_PROMPT_TEMPLATE)
    print(GOOGLE_APPLICATION_CREDENTIALS)
    print(GOOGLE_OAUTH_CREDENTIALS_FILE)
    print(GOOGLE_OAUTH_TOKEN_FILE)
    print(SERVICE_ACCOUNT_SANDBOX_FOLDER)

