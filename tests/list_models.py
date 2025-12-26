import os
from google import genai
from src.settings import settings

def listar_modelos_disponibles():
    print(f"🔍 Conectando a Vertex AI en: {settings.gcp_project_id} (us-central1)...")
    
    # Usamos el cliente nuevo que ya tienes instalado
    client = genai.Client(
        vertexai=True, 
        project=settings.gcp_project_id, 
        location="us-central1"
    )

    print("\n📋 --- LISTA DE MODELOS GEMINI ---")
    
    # Esta función lista todos los modelos disponibles para tu cuenta
    try:
        # Paginador de modelos
        pager = client.models.list() 
        
        found_any = False
        for model in pager:
            # El nombre viene completo, ej: publishers/google/models/gemini-1.5-flash
            full_name = model.name
            
            # Filtramos solo los que nos interesan
            if "gemini" in full_name.lower():
                # Extraemos solo el ID final (lo que va después de 'models/')
                model_id = full_name.split('/')[-1]
                
                # Resaltamos si parece ser el que buscas (Flash + 3 o 2025)
                if "flash" in model_id and ("3" in model_id or "exp" in model_id):
                    print(f" 🔥 \033[92m{model_id}\033[0m (Posible candidato)")
                else:
                    print(f"    {model_id}")
                found_any = True
        
        if not found_any:
            print("⚠️ No se encontraron modelos con el nombre 'gemini'. Revisa permisos.")

    except Exception as e:
        print(f"❌ Error al listar: {e}")

if __name__ == "__main__":
    listar_modelos_disponibles()