# src/transcription/merge_transcriptions_in_memory.py}
# Librerias internas
import re
from typing import List, Tuple

def parse_timestamp_to_ms(timestamp: str) -> int:
    parts = timestamp.split(":")
    if len(parts) == 2:  # MM:SS
        minutes, seconds = map(int, parts)
        return (minutes * 60 + seconds) * 1000
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = map(int, parts)
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    return 0

def format_timestamp(ms: int) -> str:
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"[{hours:02}:{minutes:02}:{seconds:02}]"
    return f"[{minutes:02}:{seconds:02}]"

def merge_transcriptions_in_memory(chunks_info: List[Tuple[str, int]]) -> str:
    """
    Une las transcripciones de los fragmentos, ajustando timestamps.

    Args:
        chunks_info: Lista de tuplas [(transcript_text, start_ms), ...]
    Returns:
        str: Transcripción completa unificada.
    """
    full_transcription_content = []

    for transcript_text, chunk_start_ms in chunks_info:
        lines = transcript_text.splitlines()
        for line in lines:
            match = re.match(r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)', line)
            if match:
                original_ts = match.group(1)
                text = match.group(2)
                adjusted_ms = chunk_start_ms + parse_timestamp_to_ms(original_ts)
                adjusted_ts = format_timestamp(adjusted_ms)
                full_transcription_content.append(f"[{adjusted_ts}] {text.strip()}\n")
            else:
                full_transcription_content.append(line + "\n")

    return "".join(full_transcription_content)
