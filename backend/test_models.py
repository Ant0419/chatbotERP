"""
Script de diagnóstico: lista todos los modelos de Gemini disponibles
para la API Key configurada en .env que soporten generateContent.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

print("=" * 70)
print("MODELOS DISPONIBLES CON generateContent")
print("=" * 70)

count = 0
for model in genai.list_models():
    if "generateContent" in [m for m in model.supported_generation_methods]:
        count += 1
        print(f"  {count:2d}. {model.name:<45s}  {model.display_name}")

print("=" * 70)
print(f"Total: {count} modelos con generateContent")
