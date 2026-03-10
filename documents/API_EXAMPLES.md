# API Examples - Transcription Service

Complete examples for testing the refactored transcription pipeline.

---

## Quick Reference

**Base URL**: `http://localhost:8080` (local) or your Cloud Run URL

**Main Endpoint**: `POST /api/transcribe`

**Authentication**: Configure service account in environment variables

---

## Example 1: Basic Audio Transcription (Auto Routing)

The router will automatically select the best engine based on file characteristics.

### Request

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE-2024-001",
    "title": "Client Meeting Recording",
    "drive_file_id": "1abc123xyz456789",
    "doc_id": "1doc987xyz654321",
    "strategy": "auto",
    "language_code": "es-MX"
  }'
```

### Response

```json
{
  "case_id": "CASE-2024-001",
  "doc_id": "1doc987xyz654321",
  "backend_used": "Gemini 2.5 Flash",
  "duration_seconds": 42.5,
  "status": "success",
  "timestamp": "2025-12-12T10:15:30.123Z",
  "output_files": {
    "google_doc": "https://docs.google.com/document/d/1doc987xyz654321/edit"
  }
}
```

**What happens**: Router analyzes the file and selects Gemini 2.5 Flash for a short mono audio file.

---

## Example 2: 8x8 Phone Call (Force STT V1)

For 8x8 stereo phone calls, force STT V1 for optimal speaker separation.

### Request

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CALL-8x8-2024-042",
    "title": "Customer Support Call - Ticket #12345",
    "drive_file_id": "1stereo_call_123",
    "doc_id": "1doc_call_456",
    "is_8x8_call": true,
    "language_code": "es-MX"
  }'
```

### Response

```json
{
  "case_id": "CALL-8x8-2024-042",
  "doc_id": "1doc_call_456",
  "backend_used": "STT V1 Stereo",
  "duration_seconds": 180.2,
  "status": "success",
  "timestamp": "2025-12-12T10:20:45.789Z",
  "output_files": {
    "google_doc": "https://docs.google.com/document/d/1doc_call_456/edit"
  }
}
```

**What happens**: `is_8x8_call: true` forces STT V1 with stereo separation (Channel 1=Agent, Channel 2=Client).

---

## Example 3: Video Transcription (.mp4)

Videos are automatically routed to Gemini for native multimodal processing.

### Request

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "VIDEO-2024-015",
    "title": "Training Video - Product Demo",
    "drive_file_id": "1video_demo_mp4_789",
    "doc_id": "1doc_video_012",
    "strategy": "auto"
  }'
```

### Response

```json
{
  "case_id": "VIDEO-2024-015",
  "doc_id": "1doc_video_012",
  "backend_used": "Gemini 2.5 Flash",
  "duration_seconds": 65.8,
  "status": "success",
  "timestamp": "2025-12-12T10:25:30.456Z",
  "output_files": {
    "google_doc": "https://docs.google.com/document/d/1doc_video_012/edit"
  }
}
```

**What happens**: Router detects .mp4 extension and routes to Gemini (no audio extraction needed).

---

## Example 4: With Google Sheets Callback

Update a Google Sheet with transcription results (status, link, engine, duration).

### Request

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE-2024-099",
    "title": "Legal Deposition Recording",
    "drive_file_id": "1audio_legal_555",
    "doc_id": "1doc_legal_777",
    "strategy": "auto",
    "sheet_callback": {
      "spreadsheet_id": "1sheet_tracker_999",
      "sheet_name": "Transcriptions Log",
      "row_index": 12,
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
  "case_id": "CASE-2024-099",
  "doc_id": "1doc_legal_777",
  "backend_used": "Gemini 2.5 Flash",
  "duration_seconds": 38.9,
  "status": "success",
  "timestamp": "2025-12-12T10:30:15.234Z",
  "output_files": {
    "google_doc": "https://docs.google.com/document/d/1doc_legal_777/edit"
  }
}
```

### Sheet Updates

After processing, row 12 of your sheet will be updated:

| ... | E (Doc Link) | F (Status) | G (Engine) | H (Duration) |
|-----|-------------|------------|------------|--------------|
| ... | [Link to Doc](https://docs...) | ✅ Transcrito | Gemini 2.5 Flash | 00:38 |

---

## Example 5: Manual Strategy Override

Force a specific engine regardless of file characteristics.

### Request (Force Gemini)

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "MANUAL-2024-005",
    "title": "Test with Manual Gemini",
    "drive_file_id": "1test_audio_321",
    "doc_id": "1doc_test_654",
    "strategy": "gemini_flash",
    "language_code": "es-MX"
  }'
```

### Request (Force STT V1)

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "MANUAL-2024-006",
    "title": "Test with Manual STT V1",
    "drive_file_id": "1test_audio_322",
    "doc_id": "1doc_test_655",
    "strategy": "stt_v1_stereo",
    "language_code": "es-MX"
  }'
```

**What happens**: Router is bypassed, and the specified engine is used directly.

---

## Example 6: Error Handling

### Request with Invalid Drive ID

```bash
curl -X POST "http://localhost:8080/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "ERROR-TEST-001",
    "title": "Test Error Handling",
    "drive_file_id": "INVALID_ID_12345",
    "doc_id": "1doc_test_999",
    "strategy": "auto"
  }'
```

### Response (Error)

```json
{
  "detail": "No se pudo descargar el archivo de Drive: File not found"
}
```

**HTTP Status**: 500 Internal Server Error

### Sheet Update (If callback configured)

| ... | F (Status) |
|-----|------------|
| ... | ❌ Error: No se pudo descargar el archivo de Drive: File not found |

---

## Example 7: Python Client

```python
import requests
import json

# API configuration
API_URL = "http://localhost:8080/api/transcribe"

# Transcription request
request_data = {
    "case_id": "PYTHON-2024-001",
    "title": "Automated Transcription Request",
    "drive_file_id": "1abc123xyz",
    "doc_id": "1doc456xyz",
    "strategy": "auto",
    "language_code": "es-MX",
    "sheet_callback": {
        "spreadsheet_id": "1sheet789xyz",
        "sheet_name": "Transcriptions",
        "row_index": 5,
        "transcript_doc_col": "E",
        "status_col": "F",
        "engine_col": "G",
        "duration_col": "H"
    }
}

# Send request
response = requests.post(
    API_URL,
    headers={"Content-Type": "application/json"},
    data=json.dumps(request_data)
)

# Check response
if response.status_code == 200:
    result = response.json()
    print(f"✅ Success: {result['case_id']}")
    print(f"   Engine: {result['backend_used']}")
    print(f"   Duration: {result['duration_seconds']:.1f}s")
    print(f"   Doc: {result['output_files']['google_doc']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(f"   Detail: {response.json()['detail']}")
```

---

## Example 8: Google Apps Script Client

```javascript
// Google Apps Script - Call Transcription API
function transcribeAudioFile(driveFileId, docId, sheetId, row) {
  const API_URL = 'https://your-api-url.run.app/api/transcribe';

  const payload = {
    'case_id': 'GAS-' + new Date().getTime(),
    'title': 'Transcription from Apps Script',
    'drive_file_id': driveFileId,
    'doc_id': docId,
    'strategy': 'auto',
    'language_code': 'es-MX',
    'sheet_callback': {
      'spreadsheet_id': sheetId,
      'sheet_name': 'Transcriptions',
      'row_index': row,
      'transcript_doc_col': 'E',
      'status_col': 'F',
      'engine_col': 'G',
      'duration_col': 'H'
    }
  };

  const options = {
    'method': 'post',
    'contentType': 'application/json',
    'payload': JSON.stringify(payload),
    'muteHttpExceptions': true
  };

  try {
    const response = UrlFetchApp.fetch(API_URL, options);
    const result = JSON.parse(response.getContentText());

    if (response.getResponseCode() === 200) {
      Logger.log('✅ Transcription successful: ' + result.case_id);
      return result;
    } else {
      Logger.log('❌ Error: ' + result.detail);
      return null;
    }
  } catch (e) {
    Logger.log('❌ Exception: ' + e.toString());
    return null;
  }
}

// Example usage
function testTranscription() {
  const driveFileId = '1abc123xyz';
  const docId = '1doc456xyz';
  const sheetId = SpreadsheetApp.getActiveSpreadsheet().getId();

  transcribeAudioFile(driveFileId, docId, sheetId, 5);
}
```

---

## Testing Checklist

### Manual Testing

- [ ] Test with short audio file (< 5 min)
  - Expected: Gemini 2.5 Flash

- [ ] Test with long stereo audio (> 25 min, 2 channels)
  - Expected: STT V1 Stereo

- [ ] Test with 8x8 call (`is_8x8_call: true`)
  - Expected: STT V1 Stereo

- [ ] Test with video file (.mp4)
  - Expected: Gemini 2.5 Flash

- [ ] Test with Sheets callback
  - Expected: All columns updated correctly

- [ ] Test with invalid Drive ID
  - Expected: Error response + Sheet error update

- [ ] Test with manual strategy override
  - Expected: Specified engine used

### Performance Testing

- [ ] Measure processing time for short audio
  - Target: < 60 seconds

- [ ] Measure processing time for long audio
  - Target: < 5 minutes for 25 min audio

- [ ] Measure processing time for video
  - Target: < 90 seconds

- [ ] Verify normalization is skipped when appropriate
  - Check logs for "Bypass de normalización"

---

## Common Scenarios

### Scenario 1: Daily Call Center Operations

**Use Case**: Transcribe 100+ customer service calls per day

**Configuration**:
```json
{
  "is_8x8_call": true,
  "strategy": "auto",
  "sheet_callback": {
    "spreadsheet_id": "YOUR_TRACKER_SHEET",
    "sheet_name": "Daily Calls",
    "row_index": "<incremental>",
    "transcript_doc_col": "E",
    "status_col": "F",
    "engine_col": "G",
    "duration_col": "H"
  }
}
```

**Expected**: All calls routed to STT V1 for best stereo separation.

### Scenario 2: Mixed Media Content

**Use Case**: Transcribe interviews (audio) and webinars (video)

**Configuration**:
```json
{
  "strategy": "auto",
  "language_code": "es-MX"
}
```

**Expected**:
- Audio: Gemini (fast, cheap)
- Video: Gemini (native support)
- Long calls: STT V1 (better quality)

### Scenario 3: Legal Depositions

**Use Case**: High-accuracy transcription of legal proceedings

**Configuration**:
```json
{
  "strategy": "stt_v1_stereo",
  "language_code": "es-MX"
}
```

**Expected**: Always use STT V1 for maximum accuracy.

---

## Troubleshooting

### Issue: "Router always selects Gemini"

**Possible Causes**:
1. Files are short (< 25 min)
2. Files are mono (1 channel)
3. `is_8x8_call` not set for phone calls

**Solution**: Check audio metadata in logs, adjust `is_8x8_call` flag.

### Issue: "Normalization taking too long"

**Possible Causes**:
1. Large file size
2. Not using Gemini bypass

**Solution**:
- Ensure native formats (.mp3, .mp4) are used
- Check logs for "Bypass de normalización"

### Issue: "Sheets not updating"

**Possible Causes**:
1. Incorrect spreadsheet ID
2. Service account lacks permissions
3. Wrong column letters

**Solution**:
- Verify spreadsheet ID in URL
- Share sheet with service account email
- Check column letters (A-Z format)

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Welcome message |
| `/health` | GET | Health check |
| `/whoami` | GET | Service account info |
| `/api/transcribe` | POST | Main transcription endpoint |
| `/docs` | GET | Swagger UI documentation |
| `/redoc` | GET | ReDoc documentation |
| `/metrics` | GET | Prometheus metrics (if enabled) |

---

Last updated: 2025-12-12
