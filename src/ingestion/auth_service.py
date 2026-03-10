# src/ingestion/auth_service.py
"""
Autenticación vía OAuth2 (credentials.json + token.json).

Flujo:
  1. Carga token.json con Credentials.from_authorized_user_file().
  2. Si el token expiró, lo refresca automáticamente usando el refresh_token.
  3. Si token.json no existe o el refresh_token es inválido, lanza un error
     claro indicando cómo regenerarlo localmente antes de desplegar.

Regeneración local (ejecutar UNA VEZ en tu máquina):
  ---------------------------------------------------
  from google_auth_oauthlib.flow import InstalledAppFlow

  SCOPES = [
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/drive",
      "https://www.googleapis.com/auth/drive.file",
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/documents",
  ]
  flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
  creds = flow.run_local_server(port=0)
  with open("token.json", "w") as f:
      f.write(creds.to_json())
  print("token.json generado.")
  ---------------------------------------------------
  Luego sube token.json a Cloud Run (ej. via Secret Manager).
"""
import json
import threading
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger(__name__)

# Cache de credenciales OAuth2 a nivel de módulo.
# Evita leer token.json y construir el cliente en cada llamada dentro del mismo proceso.
_creds_cache: Optional[Credentials] = None
_creds_lock = threading.Lock()

# Todos los scopes que el token.json debe contener.
# Deben coincidir EXACTAMENTE con los usados al generar el token localmente.
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",   # Vertex AI / Gemini
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


def get_oauth2_credentials() -> Credentials:
    """
    Carga y refresca credenciales OAuth2 desde token.json.

    Las credenciales se cachean en memoria (módulo) para evitar lecturas
    repetidas de disco en cada request. El cache se invalida automáticamente
    cuando el token expira (creds.valid == False).

    Returns:
        Credentials: objeto listo para usarse con Google APIs y Vertex AI.

    Raises:
        FileNotFoundError: si token.json no existe.
        RuntimeError: si el token no puede refrescarse (usuario debe regenerarlo).
    """
    global _creds_cache

    with _creds_lock:
        # Retornar credenciales cacheadas si aún son válidas (no expiradas)
        if _creds_cache is not None and _creds_cache.valid:
            return _creds_cache

        # --- Origen de las credenciales ---
        # Prioridad 1: variable de entorno OAUTH2_TOKEN_JSON (Secret Manager en Cloud Run)
        # Prioridad 2: archivo oauth2_token_file (desarrollo local)
        if settings.oauth2_token_json:
            try:
                token_info = json.loads(settings.oauth2_token_json)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    "OAUTH2_TOKEN_JSON contiene JSON inválido. "
                    "Verifica que el secreto se copió correctamente."
                ) from e
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            source = "variable de entorno OAUTH2_TOKEN_JSON"
        else:
            token_path = Path(settings.oauth2_token_file)
            if not token_path.exists():
                raise FileNotFoundError(
                    f"No se encontró '{token_path}' y OAUTH2_TOKEN_JSON no está definida. "
                    "Genera el token localmente con InstalledAppFlow.run_local_server() "
                    "y despliega token.json en Cloud Run (p.ej. via Secret Manager). "
                    "Consulta el docstring de este módulo para el script completo."
                )
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            source = f"archivo '{token_path}'"

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Token OAuth2 refrescado exitosamente.")
                    # Intentar persistir solo si se usa archivo local.
                    if not settings.oauth2_token_json:
                        try:
                            token_path.write_text(creds.to_json(), encoding="utf-8")  # type: ignore[possibly-undefined]
                            logger.info("token.json actualizado en disco.")
                        except OSError as write_err:
                            logger.warning(
                                "No se pudo persistir token.json (%s). "
                                "Se usará en memoria para esta ejecución.",
                                write_err,
                            )
                except RefreshError as e:
                    raise RuntimeError(
                        "El token OAuth2 expiró y no pudo refrescarse automáticamente. "
                        "Regenera token.json localmente y vuelve a desplegarlo en Cloud Run."
                    ) from e
            else:
                raise RuntimeError(
                    "Credenciales OAuth2 inválidas y sin refresh_token disponible. "
                    "Regenera token.json localmente y vuelve a desplegarlo."
                )

        logger.info("Credenciales OAuth2 válidas cargadas desde %s.", source)
        _creds_cache = creds
        return creds


def get_google_creds_service():
    """
    Autentica vía OAuth2 y construye los servicios de Google APIs
    (Drive v3, Docs v1, Sheets v4).

    Returns:
        tuple: (drive_service, docs_service, sheets_service, creds)
    """
    try:
        creds = get_oauth2_credentials()

        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)
        sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        logger.info("✅ Servicios Google (Drive/Docs/Sheets) inicializados con OAuth2.")
        return drive_service, docs_service, sheets_service, creds

    except Exception as e:
        logger.exception("❌ Error autenticando con OAuth2: %s", e)
        raise
