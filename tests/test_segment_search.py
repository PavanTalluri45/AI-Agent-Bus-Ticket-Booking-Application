from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from bus_booking_ai_agent.config.database import engine
import bus_booking_ai_agent.phase_03_mcp.tools.search_buses as search_buses_module
from bus_booking_ai_agent.phase_03_mcp.tools.search_buses import (
    SearchBusesInput,
    search_buses,
)
from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    BookingContext,
    _resolve_selected_bus,
    ensure_selected_schedule_details,
    resolve_booking_context,
    update_booking_context_from_tool_result,
)
from main import _build_agent_payload

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def test_segment_search_suryapet_to_khammam_same_day():
    """Verify segment search finds buses between intermediate route stops (Suryapet to Khammam)."""
    try:
        connection = engine.connect()
    except SQLAlchemyError as error:
        pytest.skip(f"Database unavailable: {error}")

    try:
        # Find a future date for Hyderabad -> Vijayawada
        row = connection.execute(
            text(
                """
                SELECT s.travel_date
                FROM schedules s
                JOIN routes r ON r.id = s.route_id
                WHERE r.origin = 'Hyderabad'
                  AND r.destination = 'Vijayawada'
                  AND s.travel_date >= CURRENT_DATE + INTERVAL '1 day'
                  AND s.status = 'SCHEDULED'
                ORDER BY s.travel_date
                LIMIT 1
                """
            )
        ).mappings().first()
        if not row:
            pytest.skip("No future scheduled buses found for Hyderabad -> Vijayawada")

        target_date = row["travel_date"]
    finally:
        connection.close()

    results = search_buses(
        SearchBusesInput(
            origin="Suryapet",
            destination="Khammam",
            travel_date=target_date,
        )
    )

    assert len(results) > 0, "Expected at least one bus for Suryapet to Khammam"
    for bus in results:
        assert bus["origin"] == "Suryapet"
        assert bus["destination"] == "Khammam"
        assert bus["route_origin"] == "Hyderabad"
        assert bus["route_destination"] == "Vijayawada"
        assert bus["is_segment_search"] is True
        assert bus["boarding_stop"]["name"] == "Suryapet"
        assert bus["dropping_stop"]["name"] == "Khammam"
        assert bus["boarding_stop_name"] == "Suryapet"
        assert bus["dropping_stop_name"] == "Khammam"
        assert bus["boarding_stop_id"]
        assert bus["dropping_stop_id"]
        assert Decimal(str(bus["fare"])) > 0
        assert bus["free_seat_count"] >= 0
        assert bus["free_seats"] == bus["free_seat_count"]
        # Forbidden field: search must NEVER name available seats as available_seats
        assert "available_seats" not in bus


def test_overnight_bus_reaching_boarding_stop_next_day(monkeypatch):
    """Verify schedule matching and display times when boarding stop is reached next day."""
    row = {
        "schedule_id": str(uuid4()),
        "travel_date": date(2026, 11, 1),
        "bus_id": str(uuid4()),
        "bus_number": "KA01AB9999",
        "bus_type": "AC Sleeper",
        "total_seats": 30,
        "operator_id": str(uuid4()),
        "operator_name": "Test Travels",
        "route_id": str(uuid4()),
        "route_origin": "CityA",
        "route_destination": "CityC",
        "boarding_stop_id": str(uuid4()),
        "boarding_stop_name": "CityB",
        "dropping_stop_id": str(uuid4()),
        "dropping_stop_name": "CityC",
        "departure_time": "01:30:00",
        "arrival_time": "05:00:00",
        "fare": Decimal("300.00"),
        "currency": "INR",
        "free_seat_count": 15,
        "_boarding_sequence": 2,
        "_dropping_sequence": 3,
        "_schedule_stops": [
            {
                "sequence_number": 1,
                "arrival_time": "22:00:00",
                "departure_time": "22:30:00",
            },
            {
                "sequence_number": 2,
                "arrival_time": "01:15:00",
                "departure_time": "01:30:00",
            },
            {
                "sequence_number": 3,
                "arrival_time": "05:00:00",
                "departure_time": "05:15:00",
            },
        ],
    }

    class FakeResult:
        def __iter__(self):
            return iter([SimpleNamespace(_mapping=row)])

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    class FakeEngine:
        @contextmanager
        def connect(self):
            yield FakeConnection()

    monkeypatch.setattr(search_buses_module, "engine", FakeEngine())

    # When passenger searches for 2026-11-02 (the date bus reaches CityB), it must match!
    ref_time = datetime(2026, 11, 1, 12, 0, tzinfo=IST)
    results = search_buses(
        SearchBusesInput(
            origin="CityB",
            destination="CityC",
            travel_date=date(2026, 11, 2),
        ),
        now=ref_time,
    )
    assert len(results) == 1
    assert results[0]["departure_display"] == "1:30 AM (next day)"
    assert results[0]["arrival_display"] == "5:00 AM (next day)"

    # When passenger searches for 2026-11-01, CityB departure is not on that date
    no_results = search_buses(
        SearchBusesInput(
            origin="CityB",
            destination="CityC",
            travel_date=date(2026, 11, 1),
        ),
        now=ref_time,
    )
    assert len(no_results) == 0


def test_departed_bus_filtering(monkeypatch):
    """Verify buses that have already departed at the boarding stop in IST are excluded."""
    ref_time = datetime(2026, 11, 5, 14, 0, tzinfo=IST)

    departed_row = {
        "schedule_id": str(uuid4()),
        "travel_date": date(2026, 11, 5),
        "bus_id": str(uuid4()),
        "bus_number": "BUS-PAST",
        "bus_type": "AC Seater",
        "total_seats": 40,
        "operator_id": str(uuid4()),
        "operator_name": "Past Travels",
        "route_id": str(uuid4()),
        "route_origin": "Start",
        "route_destination": "End",
        "boarding_stop_id": str(uuid4()),
        "boarding_stop_name": "Start",
        "dropping_stop_id": str(uuid4()),
        "dropping_stop_name": "End",
        "departure_time": "10:00:00",  # 10:00 AM is before 14:00 (departed)
        "arrival_time": "18:00:00",
        "fare": Decimal("200.00"),
        "currency": "INR",
        "free_seat_count": 20,
        "_boarding_sequence": 1,
        "_dropping_sequence": 2,
        "_schedule_stops": [
            {
                "sequence_number": 1,
                "arrival_time": "09:45:00",
                "departure_time": "10:00:00",
            },
            {
                "sequence_number": 2,
                "arrival_time": "18:00:00",
                "departure_time": "18:15:00",
            },
        ],
    }

    upcoming_row = {
        "schedule_id": str(uuid4()),
        "travel_date": date(2026, 11, 5),
        "bus_id": str(uuid4()),
        "bus_number": "BUS-FUTURE",
        "bus_type": "AC Seater",
        "total_seats": 40,
        "operator_id": str(uuid4()),
        "operator_name": "Future Travels",
        "route_id": str(uuid4()),
        "route_origin": "Start",
        "route_destination": "End",
        "boarding_stop_id": str(uuid4()),
        "boarding_stop_name": "Start",
        "dropping_stop_id": str(uuid4()),
        "dropping_stop_name": "End",
        "departure_time": "16:00:00",  # 4:00 PM is after 14:00 (upcoming)
        "arrival_time": "23:00:00",
        "fare": Decimal("220.00"),
        "currency": "INR",
        "free_seat_count": 25,
        "_boarding_sequence": 1,
        "_dropping_sequence": 2,
        "_schedule_stops": [
            {
                "sequence_number": 1,
                "arrival_time": "15:45:00",
                "departure_time": "16:00:00",
            },
            {
                "sequence_number": 2,
                "arrival_time": "23:00:00",
                "departure_time": "23:15:00",
            },
        ],
    }

    class FakeResult:
        def __iter__(self):
            return iter([SimpleNamespace(_mapping=departed_row), SimpleNamespace(_mapping=upcoming_row)])

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    class FakeEngine:
        @contextmanager
        def connect(self):
            yield FakeConnection()

    monkeypatch.setattr(search_buses_module, "engine", FakeEngine())

    results = search_buses(
        SearchBusesInput(
            origin="Start",
            destination="End",
            travel_date=date(2026, 11, 5),
        ),
        now=ref_time,
    )

    # Departed bus must be excluded; only the upcoming bus should remain
    assert len(results) == 1
    assert results[0]["bus_number"] == "BUS-FUTURE"


def test_stops_in_wrong_order_returns_empty():
    """Verify searching for stops in reverse/wrong sequence returns an empty list without guessing."""
    results = search_buses(
        SearchBusesInput(
            origin="Khammam",
            destination="Suryapet",
            travel_date=date(2026, 11, 1),
        )
    )
    assert results == []


def test_bus_selected_from_segment_results_skips_stop_picker():
    """Verify selecting a bus from segment search results auto-sets stops and bypasses stop picker."""
    boarding_id = str(uuid4())
    dropping_id = str(uuid4())
    schedule_id = str(uuid4())

    segment_bus = {
        "schedule_id": schedule_id,
        "bus_number": "TS09UH1150",
        "bus_type": "Super Luxury",
        "operator_name": "TSRTC",
        "travel_date": "2026-11-01",
        "origin": "Suryapet",
        "destination": "Khammam",
        "route_origin": "Hyderabad",
        "route_destination": "Vijayawada",
        "is_segment_search": True,
        "boarding_stop_id": boarding_id,
        "boarding_stop_name": "Suryapet",
        "dropping_stop_id": dropping_id,
        "dropping_stop_name": "Khammam",
        "departure_display": "10:00 AM",
        "arrival_display": "12:00 PM",
        "fare": "195.00",
        "free_seat_count": 12,
        "free_seats": 12,
    }

    initial_context: BookingContext = {
        "options_kind": "bus",
        "options_fresh": True,
        "available_schedules": [segment_bus],
    }

    resolved = _resolve_selected_bus(initial_context, "Select option 1")

    # Stops must be auto-populated
    assert resolved.get("schedule_id") == schedule_id
    assert resolved.get("boarding_stop_id") == boarding_id
    assert resolved.get("dropping_stop_id") == dropping_id
    assert resolved.get("boarding_stop_name") == "Suryapet"
    assert resolved.get("dropping_stop_name") == "Khammam"

    # Stop picker options must be cleared/skipped
    assert "options_kind" not in resolved
    assert "options_fresh" not in resolved


def test_bus_options_user_facing_wording_available_seats():
    """Verify bus card labels display 'available seats' instead of 'seats free'."""
    context = {
        "options_kind": "bus",
        "options_fresh": True,
        "available_schedules": [
            {
                "schedule_id": str(uuid4()),
                "bus_number": "KA01AB1234",
                "bus_type": "AC Seater",
                "operator_name": "Orange Travels",
                "departure_time": "20:00:00",
                "departure_day_offset": 0,
                "departure_display": "8:00 PM",
                "arrival_time": "23:00:00",
                "arrival_day_offset": 0,
                "arrival_display": "11:00 PM",
                "fare": "550.00",
                "free_seat_count": 8,
                "free_seats": 8,
            }
        ],
    }

    payload, metadata = _build_agent_payload(
        {"final_response": "Here are buses.", "booking_context": context},
        "conv-test",
    )

    detail = payload["options"]["items"][0]["detail"]
    assert "8 available seats" in detail
    assert "seats free" not in detail
    assert "available_seats" not in detail
