from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_03_mcp.tools.check_seat_availability import (
    CHECK_SEAT_AVAILABILITY_SQL,
)
import bus_booking_ai_agent.phase_03_mcp.tools.search_buses as search_buses_module
from bus_booking_ai_agent.phase_03_mcp.tools.search_buses import SearchBusesInput


TEST_USER_ID = "7803ebf4-7421-495d-b186-ec01c7c591c3"


def test_search_buses_returns_exact_overnight_display_times(monkeypatch):
    row = {
        "departure_time": "20:30:00",
        "arrival_time": "06:30:00",
        "_boarding_sequence": 1,
        "_dropping_sequence": 2,
        "_schedule_stops": [
            {
                "sequence_number": 1,
                "arrival_time": "20:15:00",
                "departure_time": "20:30:00",
            },
            {
                "sequence_number": 2,
                "arrival_time": "06:30:00",
                "departure_time": "06:35:00",
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
    results = search_buses_module.search_buses(
        SearchBusesInput(
            origin="Hyderabad",
            destination="Chennai",
            travel_date="2026-10-26",
        )
    )

    assert results[0]["departure_display"] == "8:30 PM"
    assert results[0]["arrival_display"] == "6:30 AM (next day)"


def test_search_buses_returns_route_data_and_excludes_overlapping_seats(
    monkeypatch,
):
    try:
        connection = engine.connect()
    except SQLAlchemyError as error:
        pytest.skip(f"PostgreSQL test database is unavailable: {error}")

    class TransactionEngine:
        @contextmanager
        def connect(self):
            yield connection

    monkeypatch.setattr(search_buses_module, "engine", TransactionEngine())
    transaction = connection.begin()
    try:
        candidates = connection.execute(
            text(
                """
                SELECT
                    s.id AS schedule_id,
                    s.travel_date,
                    r.origin,
                    r.destination,
                    boarding.id AS boarding_stop_id,
                    boarding.sequence_number AS boarding_sequence,
                    dropping.id AS dropping_stop_id,
                    dropping.sequence_number AS dropping_sequence,
                    fare.amount AS fare
                FROM schedules s
                JOIN routes r ON r.id = s.route_id
                JOIN route_stops boarding
                    ON boarding.route_id = r.id
                   AND boarding.stop_name = r.origin
                   AND boarding.is_active = TRUE
                   AND boarding.is_boarding_allowed = TRUE
                JOIN route_stops dropping
                    ON dropping.route_id = r.id
                   AND dropping.stop_name = r.destination
                   AND dropping.is_active = TRUE
                   AND dropping.is_dropping_allowed = TRUE
                   AND boarding.sequence_number < dropping.sequence_number
                JOIN fares fare
                    ON fare.schedule_id = s.id
                   AND fare.boarding_stop_id = boarding.id
                   AND fare.dropping_stop_id = dropping.id
                   AND fare.is_active = TRUE
                WHERE s.status = 'SCHEDULED'
                ORDER BY s.travel_date, r.origin, r.destination
                """
            )
        ).mappings().all()

        selected = None
        available_seats = []
        for candidate in candidates:
            parameters = {
                "schedule_id": str(candidate["schedule_id"]),
                "boarding_stop_id": str(candidate["boarding_stop_id"]),
                "dropping_stop_id": str(candidate["dropping_stop_id"]),
            }
            rows = connection.execute(
                text(CHECK_SEAT_AVAILABILITY_SQL),
                parameters,
            ).mappings().all()
            available_seats = [
                row for row in rows if row["status"] == "available"
            ]
            if len(available_seats) >= 2:
                selected = candidate
                break

        if selected is None:
            pytest.skip("No scheduled full-route fare has two free seats.")

        request = SearchBusesInput(
            origin=selected["origin"],
            destination=selected["destination"],
            travel_date=selected["travel_date"],
        )
        baseline_results = search_buses_module.search_buses(request)
        baseline = next(
            item
            for item in baseline_results
            if str(item["schedule_id"]) == str(selected["schedule_id"])
        )

        assert baseline["fare"] == selected["fare"]
        assert baseline["departure_time"] is not None
        assert baseline["arrival_time"] is not None
        assert baseline["total_seats"] >= baseline["free_seats"]

        confirmed_seat, held_seat = available_seats[:2]
        booking_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO bookings (
                    id, booking_reference, auth_user_id, schedule_id,
                    boarding_stop_id, dropping_stop_id, passenger_count,
                    total_amount, status
                ) VALUES (
                    :id, :booking_reference, :auth_user_id, :schedule_id,
                    :boarding_stop_id, :dropping_stop_id, 1, 1, 'CONFIRMED'
                )
                """
            ),
            {
                "id": booking_id,
                "booking_reference": f"SEARCH-TEST-{uuid4().hex}",
                "auth_user_id": TEST_USER_ID,
                "schedule_id": selected["schedule_id"],
                "boarding_stop_id": selected["boarding_stop_id"],
                "dropping_stop_id": selected["dropping_stop_id"],
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO booking_seats (
                    booking_id, seat_id, passenger_name, passenger_age,
                    passenger_gender, fare
                ) VALUES (
                    :booking_id, :seat_id, 'Search Test', 30, 'OTHER', 1
                )
                """
            ),
            {
                "booking_id": booking_id,
                "seat_id": confirmed_seat["seat_id"],
            },
        )
        now = datetime.now(timezone.utc)
        connection.execute(
            text(
                """
                INSERT INTO seat_holds (
                    auth_user_id, schedule_id, seat_id,
                    boarding_stop_id, dropping_stop_id,
                    boarding_sequence, dropping_sequence,
                    status, expires_at, created_at
                ) VALUES (
                    :auth_user_id, :schedule_id, :seat_id,
                    :boarding_stop_id, :dropping_stop_id,
                    :boarding_sequence, :dropping_sequence,
                    'ACTIVE', :expires_at, :created_at
                )
                """
            ),
            {
                "auth_user_id": TEST_USER_ID,
                "schedule_id": selected["schedule_id"],
                "seat_id": held_seat["seat_id"],
                "boarding_stop_id": selected["boarding_stop_id"],
                "dropping_stop_id": selected["dropping_stop_id"],
                "boarding_sequence": selected["boarding_sequence"],
                "dropping_sequence": selected["dropping_sequence"],
                "expires_at": now + timedelta(minutes=10),
                "created_at": now,
            },
        )

        results_with_conflicts = search_buses_module.search_buses(request)
        updated = next(
            item
            for item in results_with_conflicts
            if str(item["schedule_id"]) == str(selected["schedule_id"])
        )

        assert updated["free_seats"] == baseline["free_seats"] - 2
    finally:
        transaction.rollback()
        connection.close()
