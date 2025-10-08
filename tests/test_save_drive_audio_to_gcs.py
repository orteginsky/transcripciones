from src.storage.upload_service import save_drive_audio_to_gcs

if __name__ == "__main__":
    audio_link = "https://drive.google.com/file/d/1RwaDHO7O0izimYbU7aov-Hcik3ixPvgE"
    nombre = "12_Alex Hernández"
    save_drive_audio_to_gcs(audio_link, nombre)