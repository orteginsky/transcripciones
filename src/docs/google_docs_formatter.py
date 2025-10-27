# src/docs/google_docs_formatter.py
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Dict, Any
from src.logging_conf import get_logger

logger = get_logger(__name__)

# [mm:ss] o [hh:mm:ss] con 1 o 2 corchetes
_TS = r"\[{1,2}\d{1,2}:\d{2}(?::\d{2})?\]{1,2}"

# 1) [tt] Speaker: contenido
SPEAKER_RE = re.compile(
    rf"^\s*({_TS})\s*([^:\[\]]{{1,80}}):\s*(.*)\s*$"
)

# 2) [tt] [Nota: ...]
NOTE_RE = re.compile(
    rf"^\s*({_TS})\s*(\[\s*Nota\s*:\s*.+\])\s*$",
    flags=re.IGNORECASE,
)

def _norm_brackets(s: str) -> str:
    """[[00:05]] -> [00:05]"""
    return s.replace("[[", "[").replace("]]", "]")

def generate_google_docs_requests(title: str, transcript_text: str) -> List[Dict[str, Any]]:
    """
    Inserta:
      - Título centrado
      - Sello de fecha
      - Transcripción línea a línea:
        * [tt] Speaker:  -> cabecera en negritas + '\n' + contenido + '\n'
        * [tt] [Nota: ..] -> línea única en itálica y gris
        * resto -> línea tal cual + '\n'
    """
    requests: List[Dict[str, Any]] = []
    current_index = 1  # inicio del body

    # 1) Título centrado
    title_text = (title or "").strip()
    if title_text:
        requests.append({"insertText": {"location": {"index": current_index}, "text": title_text}})
        requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": current_index, "endIndex": current_index + len(title_text)},
                "paragraphStyle": {"alignment": "START"},
                "fields": "alignment",
            }
        })
        current_index += len(title_text)

    # 2) Sello fecha
    date_str = f"\nProcesado el {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    requests.append({"insertText": {"location": {"index": current_index}, "text": date_str}})
    current_index += len(date_str)

    # 3) Transcripción
    for raw_line in transcript_text.splitlines():
        line = raw_line.rstrip("\r")
        if not line.strip():
            requests.append({"insertText": {"location": {"index": current_index}, "text": "\n"}})
            current_index += 1
            continue

        # --- Caso 2: Nota completa ---
        m_note = NOTE_RE.match(line)
        if m_note:
            ts_raw, note_raw = m_note.groups()
            ts = _norm_brackets(ts_raw)
            note = note_raw.strip()
            text = f"{ts} {note}\n"

            # Insertar línea de nota
            requests.append({"insertText": {"location": {"index": current_index}, "text": text}})
            # Estilo itálica + gris para toda la línea
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": current_index, "endIndex": current_index + len(text) - 1},  # sin el \n
                    "textStyle": {"italic": True, "foregroundColor": {"color": {"rgbColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}},
                    "fields": "italic,foregroundColor",
                }
            })
            current_index += len(text)
            continue

        # --- Caso 1: Cabecera Speaker ---
        m_spk = SPEAKER_RE.match(line)
        if m_spk:
            ts_raw, speaker, content = m_spk.groups()
            ts = _norm_brackets(ts_raw)
            header = f"{ts} {speaker.strip()}:"

            # a) Cabecera + \n
            header_with_nl = header + "\n"
            requests.append({"insertText": {"location": {"index": current_index}, "text": header_with_nl}})
            # b) Negritas EXACTAS de cabecera (sin \n)
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": current_index, "endIndex": current_index + len(header)},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })
            current_index += len(header_with_nl)

            # c) Contenido (si lo hay) + \n
            content_text = (content or "").strip()
            content_with_nl = content_text + "\n"
            requests.append({"insertText": {"location": {"index": current_index}, "text": content_with_nl}})
            current_index += len(content_with_nl)
            continue

        # --- Resto de líneas (no reconocidas) ---
        text_to_insert = line.strip() + "\n"
        requests.append({"insertText": {"location": {"index": current_index}, "text": text_to_insert}})
        current_index += len(text_to_insert)

    logger.info("Requests de formato generados. Total: %d", len(requests))
    # Asegurar alineación izquierda para todo el documento
    requests.append({
        "updateParagraphStyle": {
            "range": {"startIndex": 1, "endIndex": current_index},
            "paragraphStyle": {"alignment": "START"},
            "fields": "alignment",
        }
    })
    return requests
