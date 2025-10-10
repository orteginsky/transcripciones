from src.docs.google_docs_quick import create_oauth_google_doc

# Ejemplo de uso:
title = "Entrevista de Juan Pérez"
transcription_text = """
[00:01] Entrevistador: ¿Cómo te llamas?
[00:05] Entrevistado: Juan Pérez
[00:10] Entrevistador: ¿De dónde eres?
[00:12] Entrevistado: Soy de México.
"""

result = create_oauth_google_doc(title=title, content=transcription_text, make_public=True)
print(result)
