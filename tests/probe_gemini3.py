import os
from google import genai
from google.genai import types
from src.settings import settings

def probe_gemini_locations():
    model_id = "gemini-3-flash-preview"
    # Lista de lugares donde Google suele desplegar betas
    locations_to_try = ["us-central1", "us-east4", "us-west1", "global"]
    
    print(f"🕵️‍♀️ Iniciando búsqueda de {model_id}...")

    for loc in locations_to_try:
        print(f"\n📍 Probando región: {loc}")
        try:
            client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=loc,
                http_options={'api_version': 'v1beta1'} # Forzamos beta siempre
            )
            
            # Prueba simple de "Hola mundo"
            response = client.models.generate_content(
                model=model_id,
                contents="Responde solo con la palabra: ÉXITO."
            )
            
            print(f"✅ ¡ENCONTRADO! El modelo funciona en: {loc}")
            print(f"🤖 Respuesta del modelo: {response.text}")
            print("\n🎉 ACCIÓN REQUERIDA:")
            print(f"Cambia tu .env a: GCP_REGION={loc}")
            return # Terminamos si encontramos uno

        except Exception as e:
            # Filtramos el mensaje de error para que no llene la pantalla
            error_msg = str(e)
            if "404" in error_msg:
                print(f"❌ 404 Not Found en {loc}")
            elif "400" in error_msg:
                # Si da 400, significa que el modelo EXISTE pero enviamos mal los datos (buena señal)
                print(f"⚠️ 400 Bad Request en {loc} (¡El modelo existe aquí! Revisa formato)")
                print(f"Detalle: {error_msg[:200]}...")
            else:
                print(f"❌ Error desconocido en {loc}: {error_msg[:100]}...")

if __name__ == "__main__":
    probe_gemini_locations()