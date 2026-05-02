"""
tests/test_gemini3_availability.py
Verifica si gemini-3-flash-preview es accesible desde distintas configuraciones.

Uso:
    # Con ADC (Application Default Credentials):
    python -m tests.test_gemini3_availability

    # Con API Key explícita:
    GOOGLE_CLOUD_API_KEY=<tu-key> python -m tests.test_gemini3_availability
"""

import os
import sys

from google import genai
from google.genai import types

# Reutilizamos el helper de producción para validar la extracción de texto
from src.transcription.vertex_service import _extract_text

MODEL = "gemini-3-flash-preview"
PROMPT = "Responde solo con la palabra: ÉXITO."

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _try(label: str, client: genai.Client) -> bool:
    """Intenta una llamada sencilla y reporta el resultado. Devuelve True si OK."""
    print(f"\n{'─'*60}")
    print(f"🔍 {label}")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=PROMPT,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=256,
            ),
        )
        text = _extract_text(response)
        print(f"✅  ÉXITO — response.text={response.text!r} | extraído={text!r}")
        return True
    except Exception as e:
        msg = str(e)
        code = "404" if "404" in msg else ("400" if "400" in msg else "ERR")
        # Truncamos para no llenar la pantalla
        print(f"❌  {code} — {msg[:300]}")
        return False


# ---------------------------------------------------------------------------
# Caso 1: API Key (igual que el snippet de Vertex AI Console)
# ---------------------------------------------------------------------------

def test_api_key():
    api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
    if not api_key:
        print("\n⚠️  GOOGLE_CLOUD_API_KEY no definida — saltando prueba con api_key")
        return False

    client = genai.Client(
        vertexai=True,
        api_key=api_key,
    )
    return _try("API Key (sin project/location — igual que snippet GCP)", client)


# ---------------------------------------------------------------------------
# Caso 2: OAuth2 / ADC con distintas combinaciones de location + api_version
# ---------------------------------------------------------------------------

def test_oauth2_variants():
    """
    Prueba las combinaciones que más suelen fallar/funcionar con Gemini preview:
      - location: global vs us-central1
      - api_version: v1beta1 vs v1
      - sin http_options
    """
    # Intentamos importar las credenciales del proyecto (OAuth2 si están disponibles)
    try:
        from src.settings import settings
        from src.ingestion.auth_service import get_oauth2_credentials
        creds = get_oauth2_credentials()
        project = settings.gcp_project_id
        print(f"\nℹ️  Usando OAuth2 — project={project}")
    except Exception as e:
        creds = None
        project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        print(f"\nℹ️  OAuth2 no disponible ({e}), usando ADC — project={project}")

    combos = [
        ("global",       "v1beta1"),
        ("global",       "v1"),
        ("global",       None),
        ("us-central1",  "v1beta1"),
        ("us-central1",  "v1"),
        ("us-central1",  None),
    ]

    found = False
    for location, api_version in combos:
        kwargs: dict = dict(
            vertexai=True,
            project=project,
            location=location,
        )
        if creds:
            kwargs["credentials"] = creds
        if api_version:
            kwargs["http_options"] = {"api_version": api_version}

        label_ver = api_version or "sin api_version"
        label = f"OAuth2/ADC — location={location} | {label_ver}"

        client = genai.Client(**kwargs)
        ok = _try(label, client)
        if ok:
            found = True
            print(f"\n🎯  CONFIGURACIÓN GANADORA:")
            print(f"    location     = {location!r}")
            print(f"    api_version  = {api_version!r}")
            break  # primera que funciona

    return found


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  Test de disponibilidad: {MODEL}")
    print(f"{'='*60}")

    found_api_key = test_api_key()
    found_oauth   = test_oauth2_variants()

    print(f"\n{'='*60}")
    if found_api_key or found_oauth:
        print("🟢  El modelo está disponible en al menos una configuración.")
        if found_api_key and not found_oauth:
            print("⚠️   Solo funciona con API Key — revisar configuración OAuth2/Vertex.")
    else:
        print("🔴  El modelo NO está disponible en ninguna configuración probada.")
        print("    Posibles causas:")
        print("    1. El modelo requiere allowlisting en tu proyecto GCP.")
        print("    2. El nombre del modelo es incorrecto para Vertex AI.")
        print("    3. Tu cuenta/SA no tiene el permiso aiplatform.endpoints.predict.")
        sys.exit(1)
