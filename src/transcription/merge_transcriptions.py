# src/transcription/merge_transcriptions.py
import re

def parse_timestamp_to_ms(timestamp: str) -> int:
    """
    Convierte un timestamp en formato [HH:MM:SS] o [MM:SS] a milisegundos.
    
    Args:
        timestamp (str): El timestamp en formato [MM:SS] o [HH:MM:SS].

    Returns:
        int: El tiempo en milisegundos.
    """
    parts = timestamp.split(":")
    if len(parts) == 2:  # [MM:SS]
        minutes, seconds = map(int, parts)
        return (minutes * 60 + seconds) * 1000
    elif len(parts) == 3:  # [HH:MM:SS]
        hours, minutes, seconds = map(int, parts)
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    return 0

def format_timestamp(ms: int) -> str:
    """
    Convierte un tiempo en milisegundos a formato [MM:SS] o [HH:MM:SS].

    Args:
        ms (int): El tiempo en milisegundos.

    Returns:
        str: El tiempo en formato [MM:SS] o [HH:MM:SS].
    """
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60

    if hours > 0:
        return f"[{hours:02}:{minutes:02}:{seconds:02}]"
    else:
        return f"[{minutes:02}:{seconds:02}]"

def merge_transcriptions(audio_base_name: str, transcription_sub_dir: str, chunks_info: list) -> str:
    """
    Unifica las transcripciones de los fragmentos, ajustando las marcas de tiempo y los hablantes.
    
    Args:
        audio_base_name (str): Nombre base del archivo de audio.
        transcription_sub_dir (str): Subdirectorio donde están las transcripciones.
        chunks_info (list): Información sobre los fragmentos, contiene rutas y tiempos de inicio.

    Returns:
        str: Transcripción completa unificada.
    """
    full_transcription_content = []
    
    # Itera sobre la lista que guardamos antes, con las rutas y los tiempos de inicio
    for transcription_path, chunk_start_ms in chunks_info:
        # Abre cada archivo de transcripción individual
        with open(transcription_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            # Busca una línea que empiece con una marca de tiempo como [00:00]
            match = re.match(r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)', line)

            if match:
                original_timestamp_str = match.group(1)  # Ej: "01:30"
                remaining_text = match.group(2)          # Ej: "Speaker 1: hola"

                # Convierte el tiempo del fragmento a milisegundos
                timestamp_in_chunk_ms = parse_timestamp_to_ms(original_timestamp_str)

                # Suma el tiempo de inicio del fragmento al tiempo local de la línea
                adjusted_timestamp_ms = chunk_start_ms + timestamp_in_chunk_ms

                # Vuelve a formatear el tiempo ya corregido
                adjusted_timestamp_str = format_timestamp(adjusted_timestamp_ms)

                # Crea la nueva línea con el tiempo ajustado
                adjusted_line = f"[{adjusted_timestamp_str}] {remaining_text.strip()}\n"
                full_transcription_content.append(adjusted_line)
            else:
                # Si la línea no tiene marca de tiempo, simplemente la añade tal cual
                full_transcription_content.append(line)

    # Devuelve la transcripción completa unificada
    return "\n".join(full_transcription_content)


