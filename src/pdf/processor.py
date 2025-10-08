# src/pdf/processor.py
import re
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import inch
from datetime import datetime

def process_transcription_text_for_pdf(text_content: str, styles):
    story = []

    # Encabezado y título
    story.append(Paragraph("TRANSCRIPCIÓN DE ENTREVISTA", styles["TitleStyle"]))
    story.append(Paragraph(datetime.now().strftime("Procesado el %d/%m/%Y %H:%M"), styles["HeaderStyle"]))
    story.append(Spacer(1, 0.3 * inch))

    lines = text_content.splitlines()

    timestamp_pattern = re.compile(r"\[(\d{1,2}:\d{2}:\d{2})\]")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        timestamp_match = timestamp_pattern.search(line)
        timestamp = timestamp_match.group(1) if timestamp_match else None

        if timestamp is not None:
            remaining_text = line[timestamp_match.end():].strip()

            speaker_match = re.match(r"([A-Za-zÁÉÍÓÚáéíóúüÜñÑ\s]+):\s*(.*)", remaining_text)
            if speaker_match:
                speaker = speaker_match.group(1).strip()
                dialogue = speaker_match.group(2).strip()

                story.append(Paragraph(f"<b>[{timestamp}] {speaker}:</b>", styles["SpeakerStyle"]))
                story.append(Paragraph(dialogue, styles["DialogueStyle"]))
            else:
                story.append(Paragraph(f"[{timestamp}] {remaining_text}", styles["DialogueStyle"]))

        elif line.startswith("[Nota:") or line.startswith("[Observación"):
            story.append(Paragraph(line, styles["NoteStyle"]))
        else:
            story.append(Paragraph(line, styles["DialogueStyle"]))

    return story
