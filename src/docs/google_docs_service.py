# src/docs/google_docs_service.py
from __future__ import annotations
from typing import Dict, Any, List
from googleapiclient.errors import HttpError
from src.ingestion.auth_service import get_google_creds_service
import copy

from src.docs.google_docs_formatter import generate_google_docs_requests

def _get_doc_end_index(docs_service, doc_id: str) -> int:
    """Devuelve el endIndex actual del body del Doc."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    # El último StructuralElement trae el endIndex total del body
    return doc["body"]["content"][-1]["endIndex"]

def _offset_requests(requests: List[Dict[str, Any]], delta: int) -> List[Dict[str, Any]]:
    """Suma 'delta' a todos los startIndex/endIndex/index de las requests."""
    adj = copy.deepcopy(requests)

    def add_delta(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("startIndex", "endIndex", "index") and isinstance(v, int):
                    node[k] = v + delta
                else:
                    add_delta(v)
        elif isinstance(node, list):
            for item in node:
                add_delta(item)

    for r in adj:
        add_delta(r)
    return adj


def append_formatted_transcript(doc_id: str, title: str, transcript_text: str) -> dict:
    """
    Aplica el formato al final del Doc:
      - título
      - sello de fecha
      - líneas con estilos (bold para cabeceras Speaker, itálica gris para notas)
      - alineación izquierda
    """
    drive_service, docs_service, creds = get_google_creds_service()

    end_idx = _get_doc_end_index(docs_service, doc_id)
    # Queremos que la PRIMERA insertText (que en el template va en index=1)
    # caiga exactamente en end_idx - 1. Por eso delta = (end_idx - 1) - 1 = end_idx - 2
    delta = max(end_idx - 2, 0)

    raw_reqs = generate_google_docs_requests(title=title, transcript_text=transcript_text)
    reqs = _offset_requests(raw_reqs, delta)

    body = {"requests": reqs}
    return docs_service.documents().batchUpdate(documentId=doc_id, body=body).execute()


def replace_with_formatted_transcript(doc_id: str, title: str, transcript_text: str) -> dict:
    drive_service, docs_service, creds = get_google_creds_service()
    end_idx = _get_doc_end_index(docs_service, doc_id)

    delete_req = {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_idx - 1}}}

    raw_reqs = generate_google_docs_requests(title=title, transcript_text=transcript_text)
    # Tras borrar, el body queda listo para insertar con el mismo truco: delta= max(new_end-2, 0)
    # pero como acabamos de borrar, el end suele ser 2 (body vacío = "\n"), así que delta=0 funciona.
    reqs = [delete_req] + _offset_requests(raw_reqs, 0)

    body = {"requests": reqs}
    return docs_service.documents().batchUpdate(documentId=doc_id, body=body).execute()


def append_text_to_google_doc(*, doc_id: str, content: str) -> Dict[str, Any]:
    """
    Inserta 'content' al final del documento 'doc_id' usando la cuenta actual
    """
    drive_service, docs_service, creds = get_google_creds_service()
    try:
        doc = docs_service.documents().get(documentId=doc_id).execute()
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
        docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
        return {"doc_id": doc_id, "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

    except HttpError as e:
        raise RuntimeError(f"Docs append failed: {e}") from e
