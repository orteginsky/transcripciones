import google.generativeai as genai

genai.configure(api_key="AIzaSyBGn5lY9pUQedFnLGsrrE3cFOU-DiHWJk4")

# Usa un modelo vigente
model = genai.GenerativeModel("gemini-2.0-flash")  # o "gemini-1.5-pro"

response = model.generate_content("Hola, ¿puedes responder este mensaje de prueba?")
print(response.text)
