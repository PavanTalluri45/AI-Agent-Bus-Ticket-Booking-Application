import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load variables from .env
load_dotenv()

# Keep the confirmed working model for the Interactions API
MODEL = "gemini-3.5-flash-lite"

# Temporary failures worth retrying on the same key.
# 429 is included because there is no second key to fail over to.
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]


def load_gemini_api_key() -> str:
    """
    Load the Gemini API key from the GEMINI_API_KEY environment variable.

    Never hardcodes the key or logs its value.
    """
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("No Gemini API key configured. Please set GEMINI_API_KEY in .env")
    return key


# SDK-level retries for transient errors (rate limit / 5xx)
http_options = types.HttpOptions(
    retry_options=types.HttpRetryOptions(
        http_status_codes=RETRY_STATUS_CODES,
        attempts=3,
        initial_delay=1.0,
        max_delay=4.0,
    )
)

# Single client used across the codebase
client = genai.Client(api_key=load_gemini_api_key(), http_options=http_options)

# Backwards-compatible alias for any code importing the old name
gemini_client_manager = client