import re


class UnsafeMemoryError(ValueError):
    """Raised when a memory value contains sensitive data."""


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "JWT/access token",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
        ),
    ),
    (
        "private key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        "password",
        re.compile(
            r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "API key",
        re.compile(
            r"\b(?:api[_ -]?key|apikey)\s*[:=]\s*[A-Za-z0-9_-]{8,}",
            re.IGNORECASE,
        ),
    ),
    (
        "access token",
        re.compile(
            r"\b(?:access[_ -]?token|refresh[_ -]?token)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "database connection string",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+:[^\s@]+@",
            re.IGNORECASE,
        ),
    ),
    (
        "secret key",
        re.compile(
            r"\b(?:secret[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
)


def validate_memory_value(memory_value: str) -> str:
    """
    Validate a memory value before it is persisted.

    User memory is intended for useful preferences and context,
    not secrets or credentials.
    """

    if not isinstance(memory_value, str):
        raise UnsafeMemoryError(
            "Memory value must be a string."
        )

    value = memory_value.strip()

    if not value:
        raise UnsafeMemoryError(
            "Memory value cannot be empty."
        )

    for label, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise UnsafeMemoryError(
                f"Memory value appears to contain sensitive data "
                f"({label}). Secrets and credentials must not be "
                f"stored as user memory."
            )

    return value