from google.cloud import speech_v2
from src.settings import GCP_PROJECT_ID

def main():
    client = speech_v2.SpeechClient()
    parent = f"projects/{GCP_PROJECT_ID}/locations/global"
    recognizers = list(client.list_recognizers(parent=parent))
    print(f"Conexión STT v2 OK. Reconocedores disponibles: {len(recognizers)}")
    for r in recognizers:
        print("-", r.name)

if __name__ == "__main__":
    main()
