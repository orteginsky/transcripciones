#src/transcription/stt_batch.py
from src.settings import GCP_PROJECT_ID, GCS_BUCKET_OUTPUT
from src.logging_conf import get_logger

from google.cloud import speech_v2


logger = get_logger(__name__)

def transcribe_from_gcs(gcs_uri: str, language: str = "es-MX") -> str:
    """
    Transcribe audio en GCS usando BatchRecognize de Speech-to-Text v2.
    """
    client = speech_v2.SpeechClient()
    parent = f"projects/{GCP_PROJECT_ID}/locations/global"
    output_uri = f"gs://{GCS_BUCKET_OUTPUT}/" # Asegúrate de que esta variable exista en tus settings

    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
        language_codes=[language],
        model="latest_long",
    )

    files = [speech_v2.BatchRecognizeFileMetadata(uri=gcs_uri)]
    request = speech_v2.BatchRecognizeRequest(
        recognizer=f"{parent}/recognizers/default",
        config=config,
        files=files,
    )

    logger.info("Enviando %s a BatchRecognize...", gcs_uri)
    operation = client.batch_recognize(request=request)
    result = operation.result()  # Espera a que termine
    logger.info("Transcripción completada")

    transcript = " ".join(
        [r.alternatives[0].transcript for r in result.results if r.alternatives]
    )
    return transcript

    # --- INICIO DE LA CORRECCIÓN (Parte 1: Especificar salida) ---
    
    # 1. Define dónde se guardarán los resultados de la transcripción en GCS.
    #    Debe ser una URI a una carpeta en tu bucket.
    #    Ejemplo: "gs://mi-bucket-de-resultados/transcripciones/"
    output_uri = f"gs://{GCS_BUCKET_OUTPUT}/" # Asegúrate de que esta variable exista en tus settings
    
    output_config = speech_v2.RecognitionOutputConfig(
        gcs_output_config=speech_v2.GcsOutputConfig(uri=output_uri),
    )

    # --- FIN DE LA CORRECCIÓN (Parte 1) ---

    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
        language_codes=[language],
        model="latest_long",
    )

    files = [speech_v2.BatchRecognizeFileMetadata(uri=gcs_uri)]
    request = speech_v2.BatchRecognizeRequest(
        recognizer=f"{parent}/recognizers/default",
        config=config,
        files=files,
        recognition_output_config=output_config, # <-- Agrega la configuración de salida a la solicitud
    )

    logger.info("Enviando %s a BatchRecognize... Los resultados se guardarán en %s", gcs_uri, output_uri)
    operation = client.batch_recognize(request=request)
    
    print("Esperando a que la operación de transcripción por lotes finalice...")
    response = operation.result() # Espera a que termine. Devuelve BatchRecognizeResponse.
    logger.info("Proceso de transcripción en la nube completado.")

    # --- INICIO DE LA CORRECCIÓN (Parte 2: Procesar el resultado) ---

    # 2. El resultado NO es el texto, sino la ubicación del archivo de resultados.
    #    Extraemos la URI del archivo JSON de la respuesta.
    #    La respuesta tiene un diccionario 'results' que mapea la URI de entrada a los metadatos de salida.
    output_file_uri = response.results[gcs_uri].uri

    logger.info("El resultado de la transcripción se guardó en: %s", output_file_uri)
    
    # 3. Descarga el archivo JSON de resultados desde GCS.
    #    Necesitamos separar el nombre del bucket y el nombre del archivo (blob).
    bucket_name, blob_name = output_file_uri.replace("gs://", "").split("/", 1)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    result_json_str = blob.download_as_text()
    result_data = json.loads(result_json_str)

    # 4. Extrae la transcripción del JSON. La estructura puede variar, pero
    #    comúnmente es una lista de resultados, cada uno con alternativas.
    transcript_parts = []
    for result in result_data.get('results', []):
        if 'alternatives' in result and len(result['alternatives']) > 0:
            transcript_parts.append(result['alternatives'][0].get('transcript', ''))

    transcript = " ".join(transcript_parts)
    
    logger.info("Transcripción extraída exitosamente.")
    return transcript

    # --- FIN DE LA CORRECCIÓN (Parte 2) ---