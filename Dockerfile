# ---------------------------------------------------------
# Dockerfile - Transcripciones (FastAPI) - Python 3.11 slim
# Imagen ligera, sin root, uvicorn como servidor
# ---------------------------------------------------------
FROM python:3.11-slim

# Ergonomía / rendimiento
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app

# (Si usarás /api/transcribe-video) instala ffmpeg
# Si no lo necesitas todavía, borra ffmpeg para una imagen aún más chica.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dependencias (mejor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 2) Código
COPY src ./src

COPY data ./data

# 3) Usuario no-root
RUN useradd -u 1001 -m appuser
USER 1001

# 4) Expose opcional (Cloud Run no lo requiere)
EXPOSE 8080

# 5) Arranque (Cloud Run inyecta $PORT)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
