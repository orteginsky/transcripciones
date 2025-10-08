# src/docs/google_docs_quick.py
from __future__ import annotations
from typing import Dict, Any

from googleapiclient.errors import HttpError
from src.ingestion.auth import get_google_creds
from src.logging_conf import get_logger
from src.docs.google_docs_formatter import generate_google_docs_requests

logger = get_logger(__name__)


def create_oauth_google_doc(title: str, content: str, make_public: bool = True) -> Dict[str, Any]:
    """
    Crea un documento de Google Docs usando autenticación OAuth local,
    agrega contenido y lo hace público (si se indica).

    Args:
        title (str): Título del documento
        content (str): Texto inicial a insertar
        make_public (bool): Si True, otorga permisos de lectura pública

    Returns:
        dict: Información del documento creado:
            {
                "doc_id": "...",
                "url": "https://docs.google.com/document/d/.../edit",
                "made_public": True/False
            }
    """
    try:
        # 1️⃣ Autenticación (OAuth local)
        logger.info("🧠 Iniciando autenticación OAuth local...")
        sheets_service, drive_service, docs_service, creds = get_google_creds()
        logger.info("✅ Autenticado correctamente con OAuth.")

        # 2️⃣ Crear documento vacío
        logger.info("📄 Creando documento: %s", title)
        doc = docs_service.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")
        logger.info("✅ Documento creado. ID: %s", doc_id)

        # 3️⃣ Insertar texto
        requests = generate_google_docs_requests(title, content)
        docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
        logger.info("📝 Texto agregado correctamente al documento.")

        # 4️⃣ Enlace del documento
        public_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info("📄 Documento disponible en: %s", public_url)

        # 5️⃣ (Opcional) Permisos públicos
        made_public = True
        if make_public:
            permission = {"type": "anyone", "role": "reader"}
            drive_service.permissions().create(fileId=doc_id, body=permission).execute()
            made_public = True
            logger.info("🌍 Permisos públicos aplicados (lectura).")

        return {
            "doc_id": doc_id,
            "url": public_url,
            "made_public": made_public,
        }

    except HttpError as e:
        logger.error("❌ Error HTTP al crear el documento: %s", e)
        raise
    except Exception as e:
        logger.exception("⚠️ Error inesperado creando documento: %s", e)
        raise


if __name__ == "__main__":
    # Ejemplo de uso directo
    title = "Prueba OAuth TMF"
    transcription_text = """
    [00:01] Entrevistador: ¿Cómo te llamas?
    [00:05] Entrevistado: Juan Pérez
    [00:10] Entrevistador: ¿De dónde eres?
    [00:12] Entrevistado: Soy de México.
    """

    result = create_oauth_google_doc(title, transcription_text, make_public=True)
    print("✅ Resultado:")
    for k, v in result.items():
        print(f"  {k}: {v}")
