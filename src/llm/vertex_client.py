# src/llm/vertex_client.py
from vertexai import init
from vertexai.generative_models import GenerativeModel

class VertexLLMClient:
    def __init__(self, project: str, location: str, model_name: str, publisher: str, **gen_cfg):
        init(project=project, location=location)
        # En Model Garden, algunos modelos se referencian como "publishers/{publisher}/models/{model_name}"
        self.model = GenerativeModel(
            name=f"publishers/{publisher}/models/{model_name}"
        )
        self.gen_cfg = gen_cfg

    def generate(self, prompt: str, system: str | None = None):
        contents = [{"role": "user", "parts": [prompt]}]
        if system:
            contents.insert(0, {"role": "system", "parts": [system]})
        resp = self.model.generate_content(
            contents=contents,
            generation_config=self.gen_cfg or {}
        )
        return resp.text  # normaliza a string
