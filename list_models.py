import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key or api_key == 'your_gemini_api_key_here':
    print("API Key not set correctly in .env")
else:
    genai.configure(api_key=api_key)
    try:
        models = genai.list_models()
        with open('available_models.txt', 'w') as f:
            for m in models:
                f.write(f"Name: {m.name}, Methods: {m.supported_generation_methods}\n")
        print("Models saved to available_models.txt")
    except Exception as e:
        print(f"Error: {e}")
