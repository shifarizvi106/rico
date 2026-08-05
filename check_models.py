import google.generativeai as genai
import os

# --- PASTE YOUR NEWEST API KEY HERE ---
GOOGLE_API_KEY = "AIzaSyD47HronnFqjqKs-KzDTH4bjxjhnBLMSL4"
# ------------------------------------

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("Successfully configured API key.")
    print("-" * 20)
    print("Available models that support 'generateContent':")

    for model in genai.list_models():
      if 'generateContent' in model.supported_generation_methods:
        print(model.name)

except Exception as e:
    print("\n--- AN ERROR OCCURRED ---")
    print(f"Failed to configure or list models. This is likely a project setup or API key issue.")
    print(f"Error details: {e}")
