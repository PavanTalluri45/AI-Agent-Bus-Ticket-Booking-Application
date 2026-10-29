import json
import re
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from main import _build_agent_payload
import bus_booking_ai_agent.phase_03_mcp.tools.get_bus_details as get_bus_details_module
from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    AGENT_SYSTEM_INSTRUCTION,
    BookingContext,
    resolve_booking_context,
    update_booking_context_from_tool_result,
)
from bus_booking_ai_agent.phase_03_mcp.tools.get_bus_details import (
    GetBusDetailsInput,
)


def test_bus_options_payload_has_details_without_ids_and_only_when_fresh():
    internal_ids = [str(uuid4()) for _ in range(4)]
    context = {
        "options_kind": "bus",
        "options_fresh": True,
        "available_schedules": [
            {
                "schedule_id": internal_ids[0],
                "bus_id": internal_ids[1],
                "operator_id": internal_ids[2],
                "route_id": internal_ids[3],
                "operator_name": "YBM Travels",
                "bus_type": "AC Seater",
                "bus_number": "KA01AB1234",
                "departure_time": "22:15:00",
                "departure_day_offset": 0,
                "departure_display": "10:15 PM",
                "arrival_time": "01:00:00",
                "arrival_day_offset": 1,
                "arrival_display": "1:00 AM (next day)",
                "fare": "350.00",
                "free_seats": 7,
                "total_seats": 40,
            }
        ],
    }

    payload, metadata = _build_agent_payload(
        {"final_response": "Choose a bus.", "booking_context": context},
        "conversation-id",
    )

    assert payload["options"] == {
        "kind": "bus",
        "items": [
            {
                "label": "YBM Travels - AC Seater (KA01AB1234)",
                "detail": "10:15 PM → 1:00 AM (next day) · ₹350.00 · 7 available seats",
            }
        ],
    }
    assert metadata["options"] == payload["options"]
    serialized_options = json.dumps(payload["options"])
    assert not re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        serialized_options,
        re.IGNORECASE,
    )
    assert "40" not in serialized_options

    stale_payload, stale_metadata = _build_agent_payload(
        {
            "final_response": "Anything else?",
            "booking_context": {**context, "options_fresh": False},
        },
        "conversation-id",
    )
    assert "options" not in stale_payload
    assert "options" not in stale_metadata


def test_combined_stop_options_resolve_both_stops_and_use_display_times():
    boarding_id = str(uuid4())
    dropping_id = str(uuid4())
    details = {
        "schedule_id": str(uuid4()),
        "operator_name": "YBM Travels",
        "bus_type": "AC Seater",
        "boarding_stops": [
            {
                "stop_id": boarding_id,
                "stop_name": "Ameerpet",
                "city": "Hyderabad",
                "sequence_number": 1,
                "arrival_time": "22:00:00",
                "departure_time": "22:15:00",
                "departure_day_offset": 0,
                "day_offset": 0,
                "departure_display": "10:15 PM",
            }
        ],
        "dropping_stops": [
            {
                "stop_id": dropping_id,
                "stop_name": "Tambaram",
                "city": "Chennai",
                "sequence_number": 2,
                "arrival_time": "01:00:00",
                "arrival_day_offset": 1,
                "day_offset": 1,
                "arrival_display": "1:00 AM (next day)",
            }
        ],
    }
    context = update_booking_context_from_tool_result(
        {},
        "get_bus_details",
        {"result": details},
    )

    assert context.get("options_kind") == "stops"
    assert context.get("options_fresh") is True

    payload, metadata = _build_agent_payload(
        {
            "final_response": "Choose your stops below.",
            "booking_context": context,
        },
        "conversation-id",
    )
    expected_options = {
        "kind": "stops",
        "boarding": [
            {
                "label": "Ameerpet",
                "city": "Hyderabad",
                "display_time": "10:15 PM",
                "sequence_number": 1,
                "selected": False,
            }
        ],
        "dropping": [
            {
                "label": "Tambaram",
                "city": "Chennai",
                "display_time": "1:00 AM (next day)",
                "sequence_number": 2,
                "selected": False,
            }
        ],
    }
    assert payload["options"] == expected_options
    assert metadata["options"] == expected_options
    assert boarding_id not in json.dumps(payload["options"])
    assert dropping_id not in json.dumps(payload["options"])

    selected = resolve_booking_context(
        context,
        "Boarding stop: Hyderabad, Dropping stop: Chennai",
    )
    assert selected.get("boarding_stop_id") == boarding_id
    assert selected.get("dropping_stop_id") == dropping_id
    assert "options_kind" not in selected
    assert "options_fresh" not in selected


def test_stop_pair_resolution_rejects_non_increasing_sequences():
    context: BookingContext = {
        "boarding_stops": [
            {
                "stop_id": "later",
                "stop_name": "Chennai",
                "sequence_number": 3,
            }
        ],
        "dropping_stops": [
            {
                "stop_id": "earlier",
                "stop_name": "Hyderabad",
                "sequence_number": 1,
            }
        ],
    }

    resolved = resolve_booking_context(
        context,
        "Boarding stop: Chennai, Dropping stop: Hyderabad",
    )

    assert "boarding_stop_id" not in resolved
    assert "dropping_stop_id" not in resolved


def test_bus_selection_keeps_stop_pair_unresolved_until_schedule_details_load():
    context: BookingContext = {
        "options_kind": "bus",
        "options_fresh": True,
        "available_schedules": [
            {
                "schedule_id": "11111111-1111-1111-1111-111111111111",
                "boarding_stop_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "boarding_stop_name": "Hyderabad",
                "dropping_stop_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "dropping_stop_name": "Bangalore",
                "route_origin": "Hyderabad",
                "route_destination": "Bangalore",
                "is_segment_search": False,
            }
        ],
    }

    selected = resolve_booking_context(context, "Select option 1")

    assert selected.get("schedule_id") == "11111111-1111-1111-1111-111111111111"
    assert selected.get("boarding_stop_id") is None
    assert selected.get("dropping_stop_id") is None
    assert "boarding_stop_name" not in selected
    assert "dropping_stop_name" not in selected
    assert "options_kind" not in selected
    assert "options_fresh" not in selected


def test_system_prompt_formats_user_facing_currency_with_rupee_symbol():
    assert "put the ₹ symbol immediately before the amount" in AGENT_SYSTEM_INSTRUCTION
    assert "Never write INR or another currency code" in AGENT_SYSTEM_INSTRUCTION


def test_get_bus_details_adds_display_times_from_stop_offsets(monkeypatch):
    boarding_id = str(uuid4())
    dropping_id = str(uuid4())
    row = {
        "_schedule_stops": [
            {
                "stop_id": boarding_id,
                "sequence_number": 1,
                "arrival_time": "20:00:00",
                "departure_time": "20:30:00",
            },
            {
                "stop_id": dropping_id,
                "sequence_number": 2,
                "arrival_time": "06:30:00",
                "departure_time": "06:35:00",
            },
        ],
        "boarding_stops": [
            {
                "stop_id": boarding_id,
                "stop_name": "Hyderabad",
                "sequence_number": 1,
                "arrival_time": "20:00:00",
                "departure_time": "20:30:00",
            }
        ],
        "dropping_stops": [
            {
                "stop_id": dropping_id,
                "stop_name": "Chennai",
                "sequence_number": 2,
                "arrival_time": "06:30:00",
                "departure_time": "06:35:00",
            }
        ],
    }

    class FakeResult:
        def fetchone(self):
            return SimpleNamespace(_mapping=row)

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    class FakeEngine:
        @contextmanager
        def connect(self):
            yield FakeConnection()

    monkeypatch.setattr(get_bus_details_module, "engine", FakeEngine())
    details = get_bus_details_module.get_bus_details(
        GetBusDetailsInput(schedule_id=uuid4())
    )

    assert details is not None
    assert details["boarding_stops"][0]["departure_display"] == "8:30 PM"
    assert details["dropping_stops"][0]["arrival_display"] == "6:30 AM (next day)"


def test_search_results_mark_bus_options_fresh():
    context = update_booking_context_from_tool_result(
        {},
        "search_buses",
        {"result": [{"schedule_id": str(uuid4())}]},
    )

    assert context.get("options_kind") == "bus"
    assert context.get("options_fresh") is True
