from datetime import datetime, timezone

from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    AGENT_SYSTEM_INSTRUCTION,
    format_hold_expiry,
)


def test_format_hold_expiry_converts_utc_to_ist():
    expiry = datetime(2026, 10, 26, 5, 54, 30, tzinfo=timezone.utc)

    assert format_hold_expiry(expiry) == "11:24 AM IST"


def test_format_hold_expiry_accepts_iso_string():
    assert format_hold_expiry("2026-10-26T18:54:30+00:00") == "12:24 AM IST"


def test_format_hold_expiry_treats_naive_datetime_as_utc():
    expiry = datetime(2026, 10, 26, 0, 0)

    assert format_hold_expiry(expiry) == "5:30 AM IST"


def test_format_hold_expiry_returns_invalid_input_unchanged():
    assert format_hold_expiry("not an ISO datetime") == "not an ISO datetime"


def test_system_prompt_requires_application_expiry_and_short_detail_requests():
    assert "Show hold expiry exactly as the application provides it" in AGENT_SYSTEM_INSTRUCTION
    assert "ask for all of them in one message" in AGENT_SYSTEM_INSTRUCTION
    assert "one at a time" not in AGENT_SYSTEM_INSTRUCTION
