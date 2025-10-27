# src/docs/google_docs_service.py
from __future__ import annotations
from typing import Dict, Any
from googleapiclient.errors import HttpError
from src.ingestion.google_auth_manager import get_drive_docs

def append_text_to_google_doc(*, doc_id: str, content: str) -> Dict[str, Any]:
    """
    Inserta 'content' al final del documento 'doc_id' usando la cuenta actual
    (SA si está configurada, OAuth local si no).
    """
    drive, docs, creds = get_drive_docs()
    try:
        doc = docs.documents().get(documentId=doc_id).execute()
        # endIndex está en el último elemento del body
        body = doc.get("body", {})
        content_arr = body.get("content", [])
        if not content_arr:
            end_index = 1
        else:
            end_index = content_arr[-1].get("endIndex", 1)

        # Añadimos dos saltos de línea antes por seguridad estética
        insert_text = f"\n\n{content}\n"

        requests = [
            {
                "insertText": {
                    "location": {"index": max(1, end_index - 1)},
                    "text": insert_text
                }
            }
        ]
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
        return {"doc_id": doc_id, "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

    except HttpError as e:
        raise RuntimeError(f"Docs append failed: {e}") from e
