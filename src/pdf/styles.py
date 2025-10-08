# src/pdf/styles.py
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def get_custom_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='TitleStyle',
        fontSize=16,
        leading=20,
        alignment=1,  # centrado
        spaceAfter=12,
        textColor=colors.HexColor("#1E3D58"),
        fontName="Helvetica-Bold"
    ))

    styles.add(ParagraphStyle(
        name='HeaderStyle',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10,
        alignment=2,  # derecha
        fontName="Helvetica-Oblique"
    ))

    styles.add(ParagraphStyle(
        name='SpeakerStyle',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#003366"),
        spaceAfter=4,
        fontName="Helvetica-Bold"
    ))

    styles.add(ParagraphStyle(
        name='DialogueStyle',
        fontSize=11,
        leading=14,
        textColor=colors.black,
        spaceAfter=6,
        fontName="Helvetica"
    ))

    styles.add(ParagraphStyle(
        name='NoteStyle',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#666666"),
        spaceAfter=5,
        leftIndent=20,
        fontName="Helvetica-Oblique"
    ))

    return styles
