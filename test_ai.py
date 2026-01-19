import os
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def test_groq():
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("Groq API Key not found")
        return
    
    print(f"Testing Groq with key: {api_key[:10]}...")
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="llama-3.3-70b-versatile",
        )
        print("Groq Success:", chat_completion.choices[0].message.content)
    except Exception as e:
        print("Groq Failed:", e)

def test_gemini():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Gemini API Key not found")
        return
    
    print(f"Testing Gemini with key: {api_key[:10]}...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello")
        print("Gemini Success:", response.text)
    except Exception as e:
        print("Gemini Failed:", e)

if __name__ == "__main__":
    test_groq()
    test_gemini()
