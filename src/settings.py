# src/settings.py
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings centralizados para el proyecto, basados en variables de entorno.

    - Lee automáticamente de .env (si existe) y del entorno del sistema.
    - Castea tipos (bool, int, float, Path, etc.) con Pydantic v2.
    - Puedes usar `settings = Settings()` o `get_settings()` (con cache).
    """

    # Configuración global de Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",         # ignora variables de entorno que no estén mapeadas
    )

    # --- GCP / Vertex ---
    gcp_project_id: str | None = Field(default=None, env="GCP_PROJECT_ID")
    gcp_region: str | None = Field(default=None, env="GCP_REGION")
    google_application_credentials: str | None = Field(
        default=None,
        env="GOOGLE_APPLICATION_CREDENTIALS",
    )

    # --- Speech-to-Text v2 ---
    stt_language_code: str = Field(default="es-MX", env="STT_LANGUAGE_CODE")
    stt_enable_diarization: bool = Field(default=True, env="STT_ENABLE_DIARIZATION")
    stt_min_speakers: int = Field(default=2, env="STT_MIN_SPEAKERS")
    stt_max_speakers: int = Field(default=2, env="STT_MAX_SPEAKERS")
    speech_location: str = Field(default="us-central1", env="SPEECH_LOCATION")
    speech_recognizer: str | None = Field(default=None, env="SPEECH_RECOGNIZER")

    # --- Motor de Transcripción ---
    # Opciones sugeridas: "stt_v1_stereo", "stt_v2_batch", "stt_v1_mono"
    transcriber_engine: str = Field(default="stt_v1_stereo", env="TRANSCRIBER_ENGINE")

    # --- Storage ---
    use_gcs: bool = Field(default=False, env="USE_GCS")
    gcs_bucket: str | None = Field(default=None, env="GCS_BUCKET")
    gcs_bucket_output: str | None = Field(default=None, env="GCS_BUCKET_OUTPUT")

    # --- Rutas locales ---
    input_dir: Path = Field(default=Path("./data/input"), env="INPUT_DIR")
    work_dir: Path = Field(default=Path("./data/work"), env="WORK_DIR")
    output_dir: Path = Field(default=Path("./data/output"), env="OUTPUT_DIR")

    # --- PDF ---
    pdf_footer_text: str = Field(default="", env="PDF_FOOTER_TEXT")
    pdf_header_text: str = Field(default="", env="PDF_HEADER_TEXT")

    # --- Audio ---
    mp3_source_dir: Path = Field(default=Path("./data/mp3"), env="MP3_SOURCE_DIR")
    wav_output_dir: Path = Field(default=Path("./data/wav16k"), env="WAV_OUTPUT_DIR")
    normalize_target_db: float = Field(default=-20.0, env="NORMALIZE_TARGET_DB")

    # --- Prompt de transcripción ---
    transcription_prompt_file: Path = Field(
        default=Path("./src/domain/prompts/transcription_prompt.md.j2"),
        env="TRANSCRIPTION_PROMPT_FILE",
    )
    
    gemini_vertex: str = Field(
        default="gemini-3-flash-preview",
        env="GEMINI_VERTEX"
    )
    # --- Service account sandbox ---
    service_account_sandbox_folder: Path = Field(
        default=Path("credencial"),
        env="SERVICE_ACCOUNT_SANDBOX_FOLDER",
    )

    # -------------------------------
    # Post-init para valores derivados
    # -------------------------------
    def model_post_init(self, __context: Any) -> None:
        """
        Ajustes después de la carga, por ejemplo:
        - Si gcs_bucket_output no está definido, usar gcs_bucket.
        """
        if self.gcs_bucket_output is None:
            self.gcs_bucket_output = self.gcs_bucket

    # -------------------------------
    # Campos computados
    # -------------------------------
    @computed_field  # type: ignore[misc]
    @property
    def transcription_prompt_template(self) -> str:
        """
        Contenido del template de transcripción.

        - Si el archivo existe, lee su contenido.
        - Si no, usa un fallback por defecto.
        """
        try:
            if self.transcription_prompt_file.exists():
                return self.transcription_prompt_file.read_text(encoding="utf-8")
        except Exception:
            # En caso de algún error de lectura, no romper la app.
            pass
        return "Transcribe el siguiente audio."


# Instancia global “por defecto”
settings = Settings()


# Opción alternativa: función con cache (útil si quieres inyección tipo FastAPI)
@lru_cache
def get_settings() -> Settings:
    return Settings()


if __name__ == "__main__":
    # Pequeño smoke test
    s = get_settings()
    print(f"GCP_PROJECT_ID: {s.gcp_project_id}")
    print(f"GCP_REGION: {s.gcp_region}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {s.google_application_credentials}")
    print(f"STT_LANGUAGE_CODE: {s.stt_language_code}")
    print(f"STT_ENABLE_DIARIZATION: {s.stt_enable_diarization}")
    print(f"SPEECH_LOCATION: {s.speech_location}")
    print(f"GCS_BUCKET: {s.gcs_bucket}")
    print(f"GCS_BUCKET_OUTPUT (efectivo): {s.gcs_bucket_output}")
    print(f"TRANSCRIPTION_PROMPT_FILE: {s.transcription_prompt_file}")
    print(f"TRANSCRIPTION_PROMPT_TEMPLATE (primeros 60 chars): {s.transcription_prompt_template[:60]!r}")
