import os
from dotenv import load_dotenv
from google import genai

# Load variables from .env
load_dotenv()

# Read Gemini API key from environment
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not configured")

# Create Gemini client
client = genai.Client(api_key=api_key)

# Keep the existing model
MODEL = "gemini-3.5-flash"
