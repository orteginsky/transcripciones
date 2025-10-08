import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import os

# --- Tu configuración ---
SERVICE_ACCOUNT_FILE = 'credentials/service_account.json'   
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SHARED_DRIVE_ID = '1T3mxaJahqUc455W1-1VCiYYEra6PO03_' # <--- REEMPLAZA CON EL ID REAL DE TU CARPETA

# --- Lógica del script ---
try:
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("No se encontró el archivo de la clave de servicio.")
        raise FileNotFoundError
    
    # Autenticación con la cuenta de servicio
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    
    docs_service = build('docs', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    title = 'Hola Mundo desde Python'
    content = 'Hola, Mundo!'

    # Crear el documento en la carpeta compartida
    print('Creando documento en la carpeta compartida...')
    document = docs_service.documents().create(body={
        'title': title,
        'parents': [SHARED_DRIVE_ID]
    }).execute()
    document_id = document.get('documentId')
    print(f'Documento creado con ID: {document_id}')
    
    # Añadir contenido (esto sigue igual)
    requests = [
        {
            'insertText': {
                'location': {
                    'index': 1,
                },
                'text': content
            }
        }
    ]
    docs_service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
    print(f'Contenido añadido: "{content}"')

    # Compartir el documento con permisos de edición (también sigue igual)
    drive_service.permissions().create(
        fileId=document_id,
        body={'type': 'anyone', 'role': 'writer'},
        fields='id'
    ).execute()
    print('Permisos de edición habilitados para cualquier persona con el enlace.')

    # Obtener el enlace (también sigue igual)
    file_metadata = drive_service.files().get(
        fileId=document_id, fields='webViewLink').execute()
    
    shareable_link = file_metadata.get('webViewLink')
    print(f'Enlace del documento: {shareable_link}')

except HttpError as error:
    print(f"Ocurrió un error: {error}")
    # Si el error es 403, revisa los logs de Google Cloud para más detalles.
except FileNotFoundError:
    print(f"Error: No se encontró el archivo de la clave de servicio en {SERVICE_ACCOUNT_FILE}")
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")