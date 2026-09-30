import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

if not api_key:
    print("ERROR: GEMINI_API_KEY is missing from .env")
    raise SystemExit(1)

print("API key found.")
print("Testing Gemini...")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Say exactly: FitBuddy Gemini test successful."
)

print("\nGemini response:")
print(response.text)