FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requerimientos e instala las dependencias
# Se usa --no-cache-dir para reducir el tamaño de la imagen
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código fuente de tu aplicación
COPY .env .env
COPY src ./src
COPY credentials ./credentials
RUN mkdir -p /app/data/work
# Cloud Run automáticamente expone el puerto que escucha el contenedor.
# Tu aplicación debe escuchar en el puerto especificado por la variable de entorno $PORT.
# Se usa 0.0.0.0 para que el servidor escuche en todas las interfaces de red.
ENV PORT=8080
CMD uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
