from src.storage.drive_uploader import upload_file_to_drive

if __name__ == "__main__":
    local_file = "./data/output/drive_uploader.txt"  # o PDF, o WAV procesado
    link = upload_file_to_drive(local_file)
    print("🔗 Archivo disponible en:", link)
