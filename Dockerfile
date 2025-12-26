# ---------------------------------------------------------
# Dockerfile - Transcripciones (FastAPI) - Python 3.11 slim
# ---------------------------------------------------------
FROM python:3.11-slim

# Ergonomía / rendimiento
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Crear el usuario no-root
RUN useradd -u 1001 -m appuser

# 2) Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 3) Copiar código
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser data ./data

# 4) [CRÍTICO] Arreglar permisos de escritura para logs
# Opción A: Crear el archivo vacío y dárselo al usuario
RUN touch /app/app.log && chown appuser:appuser /app/app.log

# Opción B (Más segura): Darle control de todo el directorio /app al usuario
RUN chown -R appuser:appuser /app

# 5) Cambiar al usuario
USER 1001

# 6) Expose
EXPOSE 8080

# 7) Arranque
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]