import os
import time
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load variables from .env
load_dotenv()

# Keep the confirmed working model for the Interactions API
MODEL = "gemini-3.5-flash-lite"

# HTTP status codes that must never trigger failover
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}
# Temporary server-side failures worth retrying on another key
SERVER_ERROR_STATUS_CODES = {500, 502, 503, 504}

# Text fragments (lowercase) that indicate rate limiting / quota problems
RATE_LIMIT_MARKERS = (
    "resource_exhausted",
    "quota exceeded",
    "rate limit",
    "rate_limit",
    "too many requests",
)
# Text fragments (lowercase) that indicate a temporary server problem
SERVER_ERROR_MARKERS = ("service unavailable", "gateway timeout")

# Programming / validation errors are never retryable
APPLICATION_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    IndexError,
    SyntaxError,
)


def load_gemini_api_keys() -> list[str]:
    """
    Load configured Gemini API keys from environment variables.

    Supports:
      - GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3, ...
      - Fallback to GEMINI_API_KEY if indexed keys are not set.

    Never hardcodes keys or logs secret values.
    """
    keys: list[str] = []

    def add_key(raw_value: Optional[str]) -> bool:
        """Add a non-empty, unique key. Returns False if the value is empty."""
        if not raw_value or not raw_value.strip():
            return False
        key = raw_value.strip()
        if key not in keys:
            keys.append(key)
        return True

    # 1. Indexed keys in order, stopping at the first gap
    index = 1
    while add_key(os.getenv(f"GEMINI_API_KEY_{index}")):
        index += 1

    # 2. Single key / fallback
    add_key(os.getenv("GEMINI_API_KEY"))

    if not keys:
        raise RuntimeError(
            "No Gemini API keys configured. Please configure GEMINI_API_KEY_1, "
            "GEMINI_API_KEY_2, GEMINI_API_KEY_3 or GEMINI_API_KEY in .env"
        )

    return keys


def _extract_status_code(exc: Exception) -> Optional[int]:
    """
    Pull an HTTP status code out of the different exception shapes
    the Gemini SDK / underlying HTTP clients can raise.
    """
    # Direct attributes on the exception
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value

    # Attributes on a wrapped response object
    for attr in ("raw_response", "response"):
        response = getattr(exc, attr, None)
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value

    return None


def is_retryable_gemini_error(exc: Exception) -> tuple[bool, str]:
    """
    Determine whether an exception is a genuinely retryable Gemini failure
    (429, RESOURCE_EXHAUSTED, rate limit, quota exceeded, or temporary 5xx).

    Returns:
        (is_retryable, reason_description)

    Does NOT fail over for:
        - 400 Bad Request / Invalid Argument
        - 401 / 403 Authentication / Authorization
        - 404 Not Found
        - 422 Unprocessable Entity
        - Python application / validation errors (ValueError, TypeError, etc.)
    """
    if isinstance(exc, APPLICATION_ERRORS):
        return False, f"Application error ({type(exc).__name__})"

    status_code = _extract_status_code(exc)

    if status_code in NON_RETRYABLE_STATUS_CODES:
        return False, f"Non-retryable client error (HTTP {status_code})"

    # Combine every piece of text we can inspect
    status_text = getattr(exc, "status", None)
    status_text = status_text if isinstance(status_text, str) else ""
    body = getattr(exc, "body", "")
    full_text = f"{exc} {status_text} {body}".lower()

    if status_code == 429:
        return True, "Rate limit / Quota exceeded (HTTP 429)"

    if any(marker in full_text for marker in RATE_LIMIT_MARKERS):
        return True, "Rate limit / Quota exceeded"

    if status_code in SERVER_ERROR_STATUS_CODES:
        return True, f"Temporary Gemini server error (HTTP {status_code})"

    if any(marker in full_text for marker in SERVER_ERROR_MARKERS):
        return True, "Temporary Gemini server error (Service Unavailable)"

    return False, f"Non-retryable error (status={status_code})"


class GeminiInteractionsProxy:
    """
    Proxy for client.interactions that routes create(...) calls
    through the GeminiClientManager failover logic.
    """

    def __init__(self, manager: "GeminiClientManager"):
        self._manager = manager

    def create(self, **kwargs: Any) -> Any:
        return self._manager.create_interaction(**kwargs)


class GeminiClientManager:
    """
    Manages multiple Gemini API clients with automatic, request-local failover.

    Sequence:
        API Key 1 -> if rate-limited / quota / 5xx ->
        API Key 2 -> if rate-limited / quota / 5xx ->
        API Key 3 -> if all fail ->
        raise RuntimeError("All configured Gemini API keys are currently rate-limited or quota-exhausted.")

    Concurrency:
        Every request starts its own fresh attempt from Key 1.
        No unsafe global state or shared mutable index.
    """

    def __init__(self, model: str = MODEL):
        self.model = model
        self._api_keys = load_gemini_api_keys()
        self._clients: list[tuple[genai.Client, str]] = self._init_clients()
        self.interactions = GeminiInteractionsProxy(self)

    def _init_clients(self) -> list[tuple[genai.Client, str]]:
        # SDK HTTP options:
        # - 429 is excluded from SDK silent retries so rate-limit errors fail
        #   immediately and our failover can move to the next key without delay.
        # - One quick retry is allowed for transient 5xx server errors.
        http_options = types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                http_status_codes=sorted(SERVER_ERROR_STATUS_CODES),
                attempts=2,
                initial_delay=0.5,
                max_delay=2.0,
            )
        )

        return [
            (genai.Client(api_key=key, http_options=http_options), f"API Key {idx}")
            for idx, key in enumerate(self._api_keys, start=1)
        ]

    @property
    def key_count(self) -> int:
        return len(self._clients)

    def create_interaction(self, **kwargs: Any) -> Any:
        """
        Create a Gemini interaction with automatic API key failover.
        Failover state is completely request-local.
        """
        total_keys = len(self._clients)
        last_error: Optional[Exception] = None

        for attempt_idx, (client, key_label) in enumerate(self._clients, start=1):
            print(f"[GEMINI] Trying {key_label} (attempt {attempt_idx}/{total_keys})...")
            t_start = time.perf_counter()

            try:
                result = client.interactions.create(**kwargs)
                print(f"[GEMINI] {key_label} succeeded in {time.perf_counter() - t_start:.2f}s")
                return result

            except Exception as exc:
                elapsed = time.perf_counter() - t_start
                last_error = exc
                retryable, reason = is_retryable_gemini_error(exc)

                if not retryable:
                    print(
                        f"[GEMINI] {key_label} encountered non-retryable error: "
                        f"{reason} after {elapsed:.2f}s. Not failing over."
                    )
                    raise

                print(f"[GEMINI] {key_label} failed ({reason}) after {elapsed:.2f}s")

                if attempt_idx < total_keys:
                    print(f"[GEMINI] Switching to {self._clients[attempt_idx][1]}")
                else:
                    print(f"[GEMINI] All {total_keys} configured Gemini API keys failed with retryable conditions.")

        raise RuntimeError(
            "All configured Gemini API keys are currently rate-limited or quota-exhausted."
        ) from last_error

    def __getattr__(self, name: str) -> Any:
        """
        Delegate any other attributes (e.g. models, aio) to the primary client.
        """
        # Private names are never delegated. This also prevents infinite
        # recursion if `_clients` is looked up before it has been set.
        if name.startswith("_"):
            raise AttributeError(f"GeminiClientManager has no attribute '{name}'")
        return getattr(self._clients[0][0], name)


# Singleton instance managing configured keys with automatic failover
gemini_client_manager = GeminiClientManager(model=MODEL)

# Drop-in replacement for existing `client` imports throughout the codebase
client = gemini_client_manager