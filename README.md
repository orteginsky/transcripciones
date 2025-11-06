# TMF Audio/Video Transcription API (GCP / Cloud Run ready)

Servicio FastAPI que:

1. **Descarga** audio/video desde Google Drive
2. **(Opcional) Normaliza** audio (volumen/formato/SR) y lo sube a GCS
3. **Transcribe** con **Gemini (Vertex)** o **Speech-to-Text v2**
4. **Escribe** la transcripción en un **Google Doc existente** (recibe `doc_id`) con **formato** (título, fecha, estilos)
5. **Guarda** copia `.txt` en GCS
6. Expone **/metrics** (Prometheus) y **/api/health**

> **Cuenta de servicio** usada en tiempo de ejecución: `drive-sheets@ortega-473114.iam.gserviceaccount.com`

---

## 🌳 Estructura clave

```
src/
  api/
    main.py
    routes/
      audio_pipeline.py        # POST /api/transcribe (audio desde Drive)
      video_pipeline.py        # POST /api/transcribe-video (video desde Drive → MP3)
    middleware/
      error_handler.py         # Formato de errores + logging
  docs/
    google_docs_formatter.py   # Genera requests de formato (título, estilos, alineación)
    google_docs_service.py     # Llama a Docs API (append / replace)
  ingestion/
    drive_loader.py            # extract_drive_id(), download_from_drive(...)
    video_audio.py             # extract_audio_to_mp3(...) con ffmpeg
    google_auth_manager.py     # get_drive_docs() (SA u OAuth - aquí usamos SA)
    auth_service.py            # Credenciales Service Account (Drive/Docs)
  orchestration/
    runner.py                  # run_transcription_pipeline_to_doc(...)
                               # run_transcription_pipeline_from_gcs(...)
  storage/
    upload_service.py          # Sube archivo local a GCS (upload_to_gcs)
    gcs_uploader.py
    gcs_cleaner.py
    audio_normalizer_service.py# Normaliza y convierte a FLAC/WAV (cuando aplica)
  transcription/
    transcribers.py            # gemini_vertex_transcribe_gcs, stt_v2_transcribe_gcs, LRO, etc.
  logging_conf.py
  metrics.py
  recognizer.py
  settings.py
```

## 🧠 Arquitectura

### 1) Vista general (flujo funcional)

```mermaid
%% 1) Vista general (flujo funcional) — ajustado a módulos reales
sequenceDiagram
    autonumber
    participant U as Cliente (Thunder/Apps Script)
    participant API as FastAPI (Cloud Run, /api/transcribe)
    participant CFG as src/settings.py (Pydantic)
    participant DR as Google Drive API
    participant GCS as Cloud Storage (gs://my-bucket-out)
    participant AU as storage/audio_normalizer_service.py
    participant SP as Speech-to-Text v2
    participant V as Vertex AI (Gemini/Claude)
    participant GD as Google Docs API
    participant GO as Google Doc destino

    Note over U,API: POST {case_id, media_link o video_link, doc_id, overrides}
    U->>API: /api/transcribe (audio) / /api/transcribe-video (video)

    Note over API,CFG: 1) Carga/validación de configuración
    API->>CFG: Leer env (GCS_BUCKET, TRANSCRIBER, STT_*, PROMPT_FILE, ...)
    CFG-->>API: OK (no-vacíos)

    Note over API,DR: 2) Descarga desde Drive
    API->>DR: download_from_drive(media_link) (ingestion/drive_loader.py)
    DR-->>API: archivo local (mp3/mp4)

    Note over API,GCS: 3) Subida base a GCS
    API->>GCS: upload_to_gcs(...) (storage/upload_service.py)
    GCS-->>API: gs://.../mp3/...

    Note over API,AU: 4) (Opcional) Normalización/segmentación
    API->>AU: a wav16k/flac (storage/audio_normalizer_service.py)
    AU-->>API: gs://.../wav16k|flac/...

    Note over API,V: 5) Transcripción
    API->>API: Seleccionar backend (header/body/env)
    alt Backend: gemini vertex
        API->>V: generateContent(audio + prompt) (transcription/transcribers.py)
        V-->>API: transcript (texto crudo)
    else Backend: stt v2
        API->>SP: Recognize (LRO) sobre wav16k|flac (transcription/transcribers.py)
        SP-->>API: transcript (texto + opcional diarización)
    end

    Note over API,V: 6) Post-proceso/format (prompt)
    API->>V: aplicar TRANSCRIPTION_PROMPT_FILE (si procede)
    V-->>API: texto final

    Note over API,GD: 7) Escritura al Google Doc
    API->>GD: batchUpdate(deleteAll + insertTop) (docs/google_docs_service.py)
    GD-->>API: OK (estilos por docs/google_docs_formatter.py)

    Note over API,GCS: 8) Artefactos a GCS
    API->>GCS: guardar .txt/.json en gs://.../audio_output/<case_id>/
    GCS-->>API: OK

    Note over API,U: 9) Respuesta y métricas
    API-->>U: {status, doc_link, gcs_paths, backend, timing}

```

### 2) Vista técnica (módulos y dependencias)

```mermaid
%% 2) Vista técnica (módulos y dependencias) — mapeo 1:1 con Estructura clave
graph LR
  %% --- Capas internas ---
  subgraph API["Capa API"]
    M[[src/api/main.py]]
    RA[[src/api/routes/audio_pipeline.py]]
    RV[[src/api/routes/video_pipeline.py]]
    EH[[src/api/middleware/error_handler.py]]
  end

  subgraph ORQ["Orquestación"]
    RUN[[src/orchestration/runner.py]]
  end

  subgraph ING["Ingesta (Drive/Video)"]
    DL[[src/ingestion/drive_loader.py]]
    VAU[[src/ingestion/video_audio.py]]
    GAM[[src/ingestion/google_auth_manager.py]]
  end

  subgraph STR["Storage / Audio"]
    UP[[src/storage/upload_service.py]]
    GU[[src/storage/gcs_uploader.py]]
    GC[[src/storage/gcs_cleaner.py]]
    AN[[src/storage/audio_normalizer_service.py]]
  end

  subgraph TRN["Transcripción"]
    TR[[src/transcription/transcribers.py]]
  end

  subgraph DOCS["Google Docs"]
    GDF[[src/docs/google_docs_formatter.py]]
    GDS[[src/docs/google_docs_service.py]]
  end

  subgraph CORE["Core / Infra"]
    AS[[src/ingestion/auth_service.py]]
    ST[[src/settings.py]]
    LG[[src/logging_conf.py]]
    MT[[src/metrics.py]]
    RC[[src/recognizer.py]]
  end

  %% Relaciones internas
  M --> RA
  M --> RV
  RA --> RUN
  RV --> RUN
  EH --> M

  RUN --> DL
  RUN --> VAU
  RUN --> UP
  RUN --> GU
  RUN --> GC
  RUN --> AN
  RUN --> TR
  RUN --> GDS
  RUN --> GDF

  DL --> GAM
  GDS --> GDF

  %% Core deps
  RA --> ST
  RV --> ST
  RUN --> ST
  DL --> ST
  TR --> ST
  UP --> ST
  AN --> ST
  GDS --> ST
  GDF --> ST

  RA --> LG
  RV --> LG
  RUN --> LG
  TR --> LG
  GDS --> LG
  UP --> LG
  AN --> LG
  DL --> LG
  MT --> LG

  %% --- Servicios externos ---
  subgraph EXT["Servicios Externos"]
    CR[[Cloud Run]]
    SA[[Service Account: drive-sheets@...]]
    AR[[Artifact Registry]]
    CL[[Cloud Logging]]
    GCS[(Cloud Storage)]
    DRV[(Google Drive API)]
    GDA[(Google Docs API)]
    STT[(Speech-to-Text v2)]
    VTX[(Vertex AI Gemini/Claude)]
  end

  %% Conexiones externas
  M -. despliegue .-> CR
  CR -. usa .-> SA
  AR -. imagen .-> CR
  LG --> CL

  UP --> GCS
  GU --> GCS
  GC --> GCS
  AN --> GCS

  DL --> DRV
  GDS --> GDA

  TR --> STT
  TR --> VTX
  AS -. credenciales/ADC .- CR
  AS -. scopes .- DRV
  AS -. scopes .- GDA
  AS -. scopes .- GCS

  %% Estilos
  classDef api fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1
  classDef orq fill:#e8f5e9,stroke:#43a047,color:#1b5e20
  classDef ing fill:#fff8e1,stroke:#f9a825,color:#f57f17
  classDef str fill:#ede7f6,stroke:#5e35b1,color:#311b92
  classDef trn fill:#f1f8e9,stroke:#7cb342,color:#33691e
  classDef docs fill:#fff3e0,stroke:#fb8c00,color:#e65100
  classDef core fill:#f3e5f5,stroke:#8e24aa,color:#4a148c
  classDef ext fill:#eceff1,stroke:#607d8b,color:#37474f

  class M,RA,RV,EH api
  class RUN orq
  class DL,VAU,GAM ing
  class UP,GU,GC,AN str
  class TR trn
  class GDF,GDS docs
  class AS,ST,LG,MT,RC core
  class CR,SA,AR,CL,GCS,DRV,GDA,STT,VTX ext

```

---

## ⚙️ Prerrequisitos

* **Python 3.11+**
* **Google Cloud Project** con APIs:

  * Google **Drive API**
  * Google **Docs API**
  * **Cloud Storage**
  * **Vertex AI** (para Gemini-Vertex) y/o **Speech-to-Text v2**
* **Service Account** con permisos:

  * Acceso **editor** al **Doc** *de destino* (lo comparte el Apps Script al crearlo)
  * Acceso a los **archivos de Drive** de origen (compartidos o en Shared Drive)
  * Permisos en **GCS bucket** (p.ej. `roles/storage.objectAdmin` sobre el bucket)
* (Opcional para video) **ffmpeg** instalado localmente o definir `FFMPEG_BIN` (ruta absoluta)

---

## 🔐 Variables de entorno (.env)

Ejemplo mínimo:

```env
# GCP / Credenciales
GCP_PROJECT_ID=ortega-473114
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credencial/sa.json

# Buckets
USE_GCS=true
GCS_BUCKET=my-bucket-out
GCS_BUCKET_OUTPUT=my-bucket-out

# Backend de transcripción (default si no hay override)
TRANSCRIBER=gemini_vertex   # gemini_vertex | stt_v2

# STT (defaults)
STT_ENGINE=google
STT_LANGUAGE_CODE=es-ES
STT_ENABLE_DIARIZATION=false
# Toggles de normalización para STT
NORMALIZE_FOR_STT=true
STT_TARGET_CODEC=flac       # flac | wav
STT_TARGET_SR=8000          # 8000 recomendado para telefonía

# Prompt (opcional)
TRANSCRIPTION_PROMPT_FILE=./src/domain/prompts/transcription_prompt.md.j2
GEMINI_API_KEY=             # (Sólo si usaras AI Studio; en Vertex no hace falta)

# (Opcional) ffmpeg
FFMPEG_BIN=C:/ffmpeg/bin/ffmpeg.exe
```

> **No** subas `sa.json` ni `.env` al repo.

---

## 🚀 Instalación y ejecución local

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Exporta/define .env (o usa dotenv)
uvicorn src.api.main:app --reload --port 8080
```

* **Health**: `GET http://127.0.0.1:8080/api/health`
* **Métricas**: `GET http://127.0.0.1:8080/metrics` (Prometheus text format)

---

## 📑 Contrato API

### 1) Transcribir **audio** de Drive → anexar al Doc

`POST /api/transcribe`

**Body**:

```json
{
  "case_id": "julio",
  "title": "eficiencia operativa",
  "media_link": "https://drive.google.com/file/d/1LJtgNV6CUwlRoxPfRAT-dJcNCRANMZMX/view?usp=drive_link",
  "doc_id": "1JgSDjvvAmgq5ChY0qAdcUDFGx28lXuPrM25x0FXmr9U",
  "language_code": "es-ES",
  "diarization": false,
  "model": "latest_long",
  "transcriber": "stt_v2"
}
```

**Headers opcionales**:

* `X-Transcriber: gemini_vertex | stt_v2`  *(tiene prioridad sobre el body)*

**Response**:

```json
{
  "case_id": "julio",
  "title": "eficiencia operativa",
  "backend": "stt_v2",
  "doc_id": "1JgSDjvvAmgq5ChY0qAdcUDFGx28lXuPrM25x0FXmr9U",
  "duration_ms": 55325,
  "timestamp": "2025-10-28T16:37:58.334123Z"
}
```

> También devuelve header `X-Backend: stt_v2 | gemini_vertex`.

### 2) Transcribir **video** de Drive → (extrae MP3) → anexar al Doc

`POST /api/transcribe-video`

**Body**:

```json
{
  "case_id": "julio",
  "title": "eficiencia operativa",
  "video_link": "https://drive.google.com/file/d/AAA.../view?usp=drive_link",
  "doc_id": "1JgSDjvvAmgq5ChY0qAdcUDFGx28lXuPrM25x0FXmr9U",
  "language_code": "es-ES",
  "transcriber": "gemini_vertex"
}
```

> Requiere **ffmpeg**. Si no está en `PATH`, define `FFMPEG_BIN`.

---

## 🎚️ Selección de backend

Orden de precedencia:

1. **Header** `X-Transcriber`
2. **Body** `transcriber`
3. **.env** `TRANSCRIBER` (por defecto)

**Valores soportados**:

* `gemini_vertex` → Consume **MP3 directo** desde GCS (rápido, sin normalizar).
* `stt_v2` → Por defecto **normaliza** a FLAC/WAV.
  Puedes desactivar la normalización con `NORMALIZE_FOR_STT=false` para consumir **MP3 directo** y ganar velocidad.

---

## 📝 Formato en Google Docs

El servicio **apendea** al final del Doc con:

* **Título** + **sello de fecha**
* Transcripción **línea a línea**, respetando:

  * `[[00:05]]` → `[00:05]`
  * Líneas tipo `[tt] Speaker: contenido` → cabecera en **negritas** y contenido debajo
  * Líneas tipo `[tt] [Nota: ...]` → **itálica** y **gris**
* Alineación **izquierda** en todo el rango insertado

> El **Apps Script** creador del Doc debe **compartir** el documento con la SA o crearlo en un **Shared Drive** accesible por la SA.

---

## 🧪 Ejemplos rápidos

### Curl (audio)

```bash
curl -X POST http://127.0.0.1:8080/api/transcribe \
  -H "Content-Type: application/json" \
  -H "X-Transcriber: stt_v2" \
  -d '{
    "case_id":"julio",
    "title":"eficiencia operativa",
    "media_link":"https://drive.google.com/file/d/1LJt.../view?usp=drive_link",
    "doc_id":"1JgSDjvvAmgq5ChY0qAdcUDFGx28lXuPrM25x0FXmr9U",
    "language_code":"es-ES"
  }'
```

### Apps Script (fetch)

```js
UrlFetchApp.fetch("http://127.0.0.1:8080/api/transcribe", {
  method: "post",
  contentType: "application/json",
  headers: { "X-Transcriber": "gemini_vertex" },
  payload: JSON.stringify({
    case_id: "julio",
    title: "eficiencia operativa",
    media_link: "https://drive.google.com/file/d/1LJt.../view?usp=drive_link",
    doc_id: "1JgSDjvvAmgq5ChY0qAdcUDFGx28lXuPrM25x0FXmr9U",
    language_code: "es-ES"
  }),
});
```

---

## 📊 Métricas y salud

* `GET /api/health` → `{ "status": "ok" }`
* `GET /metrics` → métricas Prometheus (latencias, conteos, errores por backend, etc.)

---

## 🧯 Errores comunes (y cómo resolver)

* **400** `Invalid insertText index` en Docs

  * Aseguramos *offset* al final del body (`endIndex - 2`). Ya contemplado en `google_docs_service.py`.
* **403/404** al descargar de Drive

  * Verifica que el **archivo** está **compartido** con la SA o vive en un **Shared Drive** accesible.
* **403** al escribir en Docs

  * Asegura que el **Doc** está compartido con la SA (editor) o en un Shared Drive.
* **ALTS creds ignored** (warning)

  * Informativo en local; ignóralo.
* **ffmpeg** no encontrado

  * Instala ffmpeg o define `FFMPEG_BIN` con la ruta del binario.

---

## 🏭 Despliegue (Cloud Run – pista rápida)

1. Agrega `ffmpeg` al contenedor si vas a usar `/api/transcribe-video`.
2. Monta `GOOGLE_APPLICATION_CREDENTIALS` como **secret** o var de entorno.
3. Concede a la **SA de ejecución** permisos en GCS y Vertex/STT según el backend.

*(Si quieres, te dejo un `Dockerfile` con ffmpeg estático en otro momento.)*

---

## 📄 Licencia

Consulta el archivo **LICENCE** en la raíz.

---

## 💬 Soporte y mantenimiento

* **Logs** enriquecidos y tiempos por fase (`metrics.py`)
* **Override** de backend por header/body
* **Toggles** de normalización en STT
* **Formato** en Docs robusto (con opción a *fallback* a texto plano si lo habilitas después)
