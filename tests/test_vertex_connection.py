from google.cloud import aiplatform
from src.settings import GCP_PROJECT_ID, GCP_REGION

def main():
    # Inicializa Vertex AI
    aiplatform.init(project=GCP_PROJECT_ID, location=GCP_REGION)

    # Simple list of models to test connection
    models = list(aiplatform.Model.list())
    print(f"Conexión exitosa. Modelos detectados: {len(models)}")
    for m in models[:3]:
        print("-", m.display_name)

if __name__ == "__main__":
    main()
