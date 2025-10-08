IMAGE_NAME=vertex-audio-app
REGION=us-central1
PROJECT_ID?=woven-operative-419903

build:
\tdocker build -t $(IMAGE_NAME) .

run:
\tdocker run --rm -p 8080:8080 --env-file .env $(IMAGE_NAME)

tag:
\tdocker tag $(IMAGE_NAME) $(REGION)-docker.pkg.dev/$(PROJECT_ID)/apps/$(IMAGE_NAME):latest

push:
\tgcloud auth configure-docker $(REGION)-docker.pkg.dev -q
\tdocker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/apps/$(IMAGE_NAME):latest

deploy:
\tgcloud run deploy $(IMAGE_NAME) \
\t--image=$(REGION)-docker.pkg.dev/$(PROJECT_ID)/apps/$(IMAGE_NAME):latest \
\t--region=$(REGION) \
\t--platform=managed \
\t--allow-unauthenticated \
\t--port=8080 \
\t--cpu=1 --memory=1Gi --concurrency=16 \
\t--max-instances=5 \
\t--set-env-vars=GCP_PROJECT_ID=$(PROJECT_ID),GCP_REGION=$(REGION),TEMP_BUCKET=vertex-audio-temp,VERTEX_MODEL_NAME=gemini-1.5-flash-002,TRANSCRIPTION_PROMPT_FILE=./src/domain/prompts/transcription_prompt.md.j2,USE_VERTEX=true
