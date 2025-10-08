# src/pdf/renderer.py
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import letter
from src.pdf.styles import get_custom_styles
from src.pdf.processor import process_transcription_text_for_pdf
from src.logging_conf import get_logger
from pathlib import Path

logger = get_logger(__name__)

def create_styled_pdf(transcription_text_path: str) -> str:
    """
    Genera un PDF formateado a partir de un archivo de texto transcrito.
    Retorna la ruta del PDF creado.
    """
    text_path = Path(transcription_text_path)
    if not text_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {text_path}")

    output_pdf = text_path.with_suffix(".pdf")

    logger.info("Generando PDF a partir de %s", text_path)

    with open(text_path, "r", encoding="utf-8") as f:
        content = f.read()

    styles = get_custom_styles()
    story = process_transcription_text_for_pdf(content, styles)

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=letter,
        leftMargin=72,
        rightMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    doc.build(story)

    logger.info("PDF generado correctamente: %s", output_pdf)
    return str(output_pdf)

if __name__ == "__main__":
    create_styled_pdf("data/test_transcription.txt")