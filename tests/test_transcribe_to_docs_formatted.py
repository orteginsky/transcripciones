# tests/test_transcribe_to_docs_formatted.py
from src.docs.google_docs_formatter import generate_google_docs_requests

if __name__ == "__main__":
    
    text = """
    [00:00:05] Entrevistador: Buenos días, ¿podría decirme su nombre completo?
    [00:00:10] Cliente: Mi nombre es Yessica Lizeth Hernández Reyes.
    [00:00:20] Entrevistador: Gracias. ¿Podría contarme cómo empezó a trabajar en ese lugar?
    [Nota: La entrevistada habla con voz baja y pausada]
    [00:01:10] Cliente: Me contrataron en una granja de pollo donde me explotaban laboralmente.    
    """

    if not text:
        print("❌ No se obtuvo texto.")
    else:
        print("✅ Transcripción completa, creando documento con formato...")
        resultado = generate_google_docs_requests(title="titulo",transcript_text=text)
        print(resultado)
