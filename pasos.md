# 🚦 Fase 1. Anclar el punto de entrada en una API (sin tocar la lógica)

**Objetivo:** que tu código actual pueda ser llamado desde FastAPI, sin modificar funciones internas.

---
https://docs.google.com/document/d/1w64h4PmvmaHLImjVqT6R6be8kItQRyU5xBmB9YVoFZs/edit?usp=drive_link

## 🧩 Fase 2. Separar validación con Pydantic (evita errores de entrada)

**Objetivo:** asegurarte de que App Script o cualquier cliente no rompa tu pipeline con datos inválidos.

👉 Qué hacer:

1. Crea `src/domain/schemas.py`.
2. Define los modelos `AudioRequest` y `AudioResponse` como en el ejemplo (solo tipado y validación).
3. En tu endpoint de la fase 1, usa estos modelos para validar y responder.

🎯 *Meta:* Si envío datos inválidos (`audio_url` sin “https://” o `case_id` vacío), FastAPI responde 422.
No toques tu `gemini.py`, solo encapsula la entrada.

---

## ⚙️ Fase 3. Extraer tu flujo existente a una función orquestadora

**Objetivo:** centralizar la ejecución de tu pipeline (descargar MP3 → convertir → transcribir).

👉 Qué hacer:

1. Crea `src/orchestration/runner.py`.
2. Mueve tu flujo actual (lo que hoy haces en `run_pipeline` o manualmente) a una función `run_audio_from_url(audio_url, case_id)`.
3. Dentro, reutiliza **exactamente** tus funciones actuales:

   * `extract_drive_id` y `download_from_drive`
   * `process_mp3_to_wav16k`
   * `split_wav_chunks`
   * `transcribe_audio_chunk`
4. No cambies sus implementaciones; solo agrúpalas.

🎯 *Meta:* la función `run_audio_from_url` usa todo tu código actual pero devuelve la transcripción completa.
Así validas que tu flujo “base” funciona idéntico, solo con un envoltorio.

---

## ☁️ Fase 4. Sustituir OAuth local por credenciales de servicio

**Objetivo:** que Cloud Run acceda a Drive/Sheets sin interacción manual.

👉 Qué hacer:

1. En `src/ingestion/auth.py`, agrega una función paralela (`get_google_creds_service`) que use `google.auth.default()`.
2. En Cloud Run, configura el Service Account con permisos:

   * `roles/drive.readonly`
   * `roles/aiplatform.user`
   * `roles/storage.admin`
3. Tu código local seguirá usando el flujo OAuth actual (`get_google_creds()`); Cloud Run usará el nuevo.

🎯 *Meta:* misma función `download_from_drive` funcionando tanto localmente como en Cloud Run.

---

## 🧠 Fase 5. Aislar los backends de transcripción (Gemini vs STT)

**Objetivo:** poder elegir entre tus dos motores (`gemini_transcriber.py` y `transcribe_wav16k`) sin cambiar el resto.

👉 Qué hacer:

1. Crea un módulo `src/transcription/selector.py`.
2. Define ahí una pequeña función que lea de settings qué backend usar:

   ```python
   if STT_ENGINE == "gemini": use transcribe_audio_chunk
   else: use transcribe_wav16k
   ```

3. En tu runner, llama a esa función abstracta (`transcribe_audio`), no directamente a Gemini.

🎯 *Meta:* puedes cambiar de motor desde `.env` sin editar código.

---

## 🧾 Fase 6. Incorporar settings como Pydantic Settings (sin romper .env)

**Objetivo:** estandarizar lectura de configuración para despliegue.

👉 Qué hacer:

1. No elimines tu `settings.py` actual todavía.
2. Crea un `src/config/settings_pydantic.py` con equivalentes de tus variables.
3. Cárgalo en el `main.py` de FastAPI para pruebas.
   Luego, migrarás poco a poco (p.ej. cuando subas a Cloud Run).

🎯 *Meta:* mantener compatibilidad total con tu `.env`, pero preparar el entorno Cloud Run limpio.

---

## 🧩 Fase 7. Integrar GCS solo para staging temporal

**Objetivo:** que los audios procesados se suban y eliminen de un bucket temporal.

👉 Qué hacer:

1. Implementa `src/storage/gcs.py` con `upload_temp_to_gcs` y `delete_gcs_blob`.
2. En tu `runner.py`, agrega esas llamadas alrededor de la conversión.
3. No cambies el resto de tu flujo (solo agrega).

🎯 *Meta:* confirmas que sube y borra el WAV sin afectar la transcripción.

---

## 🧱 Fase 8. Dockerizar y desplegar en Cloud Run

**Objetivo:** llevar tu proyecto intacto al entorno gestionado de GCP.

👉 Qué hacer:

1. Usa tu `requirements.txt` actual, añadiendo `ffmpeg` en el Dockerfile.
2. Copia tu código a `/app/src`.
3. Expón el servicio en el puerto `8080`.

🎯 *Meta:* tu endpoint `/process-audio` se ejecuta igual que localmente, pero en Cloud Run.

---

## 🧩 Fase 9. Pruebas y validación por etapas

**Objetivo:** verificar que nada se rompe a medida que envuelves tu código.

👉 Orden de pruebas:

1. Prueba local con `uvicorn src.api.main:app --reload`.
2. Test unitario de `/health` y `/process-audio` con un archivo corto.
3. Verifica logs (`app.log`) y salida del pipeline.
4. Despliega a Cloud Run con variables `.env` equivalentes.

---

## 📍Resumen visual del enfoque progresivo

| Fase | Enfoque                | Qué cambias                        | Qué se mantiene                |
| ---- | ---------------------- | ---------------------------------- | ------------------------------ |
| 1    | Exponer API            | Creas FastAPI con `/process-audio` | Tu flujo actual                |
| 2    | Validar inputs         | Añades Pydantic models             | Código funcional intacto       |
| 3    | Orquestar pipeline     | Envuelves funciones existentes     | Ninguna lógica interna         |
| 4    | Autenticación GCP      | Añades `get_google_creds_service`  | OAuth actual                   |
| 5    | Abstracción STT/Gemini | Crea selector backend              | Transcriptores actuales        |
| 6    | Config moderna         | Añades Pydantic Settings           | `settings.py` actual operativo |
| 7    | GCS temporal           | Añades almacenamiento              | Flujo base intacto             |
| 8    | Docker & Run           | Empaquetas                         | Lógica de app intacta          |
| 9    | Pruebas                | Ejecución controlada               | Todo validado                  |

---

¿Quieres que te ayude **a identificar qué función concreta usar como pipeline principal** (para encapsular en la API) y cómo hacer el primer test `/process-audio` sin romper tu entorno actual? Puedo guiarte paso 1 con ejemplos mínimos de integración y pruebas locales.
