# Deployment Guide - Refactored Transcription Pipeline

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Google Cloud Project with:
  - Cloud Storage API enabled
  - Speech-to-Text API enabled
  - Vertex AI API enabled
  - Google Docs API enabled
  - Google Sheets API enabled
- Service Account with appropriate permissions

### 2. Local Testing

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
python test_refactored_pipeline.py

# Expected output: 9/9 tests passed ✅
```

### 3. Environment Configuration

Create/update [.env](.env) file:

```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Storage
GCS_BUCKET=your-bucket-name

# Speech-to-Text
STT_LANGUAGE_CODE=es-MX
STT_ENABLE_DIARIZATION=true
STT_MIN_SPEAKERS=2
STT_MAX_SPEAKERS=2

# Optional: Metrics
METRICS_ENABLED=true
```

### 4. Start the API Locally

```bash
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

Access API documentation:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

---

## API Usage

### Basic Transcription (Auto Routing)

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE-2024-001",
    "title": "Client Meeting",
    "drive_file_id": "1abc123xyz",
    "doc_id": "1doc456xyz",
    "strategy": "auto"
  }'
```

### With Google Sheets Callback

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE-2024-002",
    "title": "Support Call",
    "drive_file_id": "1abc123xyz",
    "doc_id": "1doc456xyz",
    "is_8x8_call": true,
    "sheet_callback": {
      "spreadsheet_id": "1sheet789xyz",
      "sheet_name": "Transcriptions",
      "row_index": 5,
      "transcript_doc_col": "E",
      "status_col": "F",
      "engine_col": "G",
      "duration_col": "H"
    }
  }'
```

### Response

```json
{
  "case_id": "CASE-2024-001",
  "doc_id": "1doc456xyz",
  "backend_used": "Gemini 2.5 Flash",
  "duration_seconds": 45.2,
  "status": "success",
  "timestamp": "2025-12-12T10:00:00.000Z",
  "output_files": {
    "google_doc": "https://docs.google.com/document/d/1doc456xyz/edit"
  }
}
```

---

## Cloud Run Deployment

### 1. Create Dockerfile (if not exists)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 2. Build and Deploy

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/transcription-api

# Deploy to Cloud Run
gcloud run deploy transcription-api \
  --image gcr.io/YOUR_PROJECT_ID/transcription-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 3600s \
  --cpu 2 \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID \
  --set-env-vars GCP_REGION=us-central1 \
  --set-env-vars GCS_BUCKET=your-bucket-name \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Configure Service Account Permissions

Your service account needs:
- `roles/storage.objectAdmin` (GCS)
- `roles/speech.client` (Speech-to-Text)
- `roles/aiplatform.user` (Vertex AI)
- Access to Google Drive, Docs, and Sheets APIs

---

## Monitoring

### Health Check

```bash
curl http://your-api-url/health
```

Expected response:
```json
{
  "status": "ok",
  "engine": "stt_v1"
}
```

### Metrics Endpoint

If `METRICS_ENABLED=true`:

```bash
curl http://your-api-url/metrics
```

Prometheus metrics include:
- `transcriptions_total{backend="stt_v1|gemini_flash"}`
- `transcriptions_errors_total{code="..."}`
- `pipeline_duration_seconds`
- `stt_phase_seconds{backend="..."}`

---

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

```
Error: Could not authenticate with Google Cloud
```

**Solution:**
- Verify `GOOGLE_APPLICATION_CREDENTIALS` is set correctly
- Check service account has required permissions
- Ensure APIs are enabled in GCP Console

#### 2. Memory Issues

```
Error: Out of memory during audio normalization
```

**Solution:**
- Increase Cloud Run memory: `--memory 4Gi`
- Enable normalization bypass for Gemini (already implemented)

#### 3. Timeout Errors

```
Error: Request timeout after 60s
```

**Solution:**
- Increase Cloud Run timeout: `--timeout 3600s`
- Use Gemini for faster transcription (auto routing handles this)

#### 4. Router Not Working

```
Error: All files going to STT V1 or Gemini
```

**Solution:**
- Check `strategy="auto"` in request
- Verify file metadata is being extracted correctly
- Check logs for routing decision reason

---

## Performance Optimization

### 1. Cost Reduction

The refactored pipeline automatically:
- Uses Gemini for short files (cheaper)
- Skips normalization when possible (faster)
- Converts to mono for Gemini (50% bandwidth)

### 2. Speed Optimization

- **Short audio/video**: Gemini (~30-60s)
- **Long stereo calls**: STT V1 (~2-5 min for 25 min audio)

### 3. Quality Optimization

The router automatically:
- Uses STT V1 for 8x8 calls (best stereo separation)
- Uses STT V1 for long stereo calls (better diarization)
- Uses Gemini for video (native multimodal)

---

## Architecture Diagram

```
┌────────────────────────────────────────┐
│        Google Apps Script             │
│     (or external trigger)             │
└─────────────┬──────────────────────────┘
              │ POST /api/transcribe
              ▼
┌────────────────────────────────────────┐
│        Cloud Run API                   │
│     (src/main.py)                     │
└─────────────┬──────────────────────────┘
              │
              ▼
┌────────────────────────────────────────┐
│     Pipeline Orchestrator              │
│  (src/orchestration/runner.py)        │
└─────────────┬──────────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌─────────┐      ┌─────────────┐
│  Drive  │      │   Router    │
│Download │      │   (Brain)   │
└─────────┘      └──────┬──────┘
                        │
              ┌─────────┴─────────┐
              │                   │
              ▼                   ▼
    ┌──────────────────┐  ┌──────────────────┐
    │    STT V1        │  │  Gemini 2.5      │
    │    (Stereo)      │  │     Flash        │
    └────────┬─────────┘  └─────────┬────────┘
             │                      │
             └──────────┬───────────┘
                        ▼
              ┌──────────────────┐
              │   Google Docs    │
              │   Formatting     │
              └─────────┬────────┘
                        ▼
              ┌──────────────────┐
              │  Google Sheets   │
              │    Callback      │
              └──────────────────┘
```

---

## Maintenance

### Regular Tasks

1. **Monitor Logs**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" --limit 50
   ```

2. **Check Metrics**
   ```bash
   # View in GCP Console > Cloud Run > Metrics
   # Or use Prometheus if exported
   ```

3. **Clean Up GCS**
   ```bash
   # Run cleanup script
   python src/maintenance/limpia_drive.py
   ```

### Updating the Pipeline

1. Make changes locally
2. Run tests: `python test_refactored_pipeline.py`
3. Commit changes
4. Redeploy to Cloud Run

---

## Support

For issues or questions:
1. Check [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
2. Review logs in GCP Console
3. Test locally with `test_refactored_pipeline.py`

---

## Version History

### v2.0 (2025-12-12) - Current
- ✅ Intelligent router/brain
- ✅ Conditional normalization
- ✅ Video support (.mp4)
- ✅ Enhanced Sheets callbacks
- ✅ Gemini 2.5 Flash integration

### v1.0 (Previous)
- Basic STT V1 transcription
- Manual strategy selection
- Always normalized audio
