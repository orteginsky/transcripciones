# tests/test_google_docs_writer_final.py
from src.docs.google_docs_writer import create_google_doc_from_transcript

if __name__ == "__main__":
    print("🧠 Probando creación de documento universal...")
    link = create_google_doc_from_transcript(
        "Prueba Final TMF",
        "Transcripción automática de prueba.\n\nTexto generado por el módulo universal."
    )
    print("✅ Documento creado:", link)
