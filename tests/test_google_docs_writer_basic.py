# tests/test_google_docs_writer_basic.py
from src.docs.google_docs_writer import create_google_doc_from_transcript

if __name__ == "__main__":
    print("🧠 Probando creación de documento en carpeta compartida...")

    text = """[00:01] Entrevistador: Hola.
[00:03] Cliente: Buen día.
[00:05] [Nota: Se escucha ruido de fondo.]
"""

    link = create_google_doc_from_transcript(
        title="Transcripción prueba TMF",
        transcript_text=text
    )
    print("✅ Documento creado y compartido:\n", link)
