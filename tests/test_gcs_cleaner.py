from src.storage.gcs_cleaner import delete_gcs_files

if __name__ == "__main__":
    uris = [
        "gs://my-bucket-out/Alex Hernández.mp3",
        "gs://my-bucket-out/processed/Alex Hernández_16k.wav"
    ]
    deleted = delete_gcs_files(uris)
    print("🧹 Eliminados:", deleted)
