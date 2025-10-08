from src.storage.gcs_uploader import upload_to_gcs
from pathlib import Path

if __name__ == "__main__":
    local_path = Path("data/wav16k/audio_prueba.wav")
    if not local_path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo: {local_path.resolve()}")
    url = upload_to_gcs(local_path)
    print("Archivo subido a:", url)
