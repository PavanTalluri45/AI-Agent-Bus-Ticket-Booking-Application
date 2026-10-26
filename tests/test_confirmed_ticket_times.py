from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import main as main_module
from bus_booking_ai_agent.config.database import engine


def test_confirmed_ticket_includes_boarding_and_overnight_dropping_times(
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

    monkeypatch.setattr(main_module, "engine", TransactionEngine())
    transaction = connection.begin()
    try:
        schedule = connection.execute(
            text(
                """
                SELECT
                    s.id AS schedule_id,
                    s.bus_id,
                    boarding.id AS boarding_stop_id,
                    dropping.id AS dropping_stop_id
                FROM schedules s
                JOIN routes r ON r.id = s.route_id
                JOIN route_stops boarding
                    ON boarding.route_id = r.id
                   AND boarding.stop_name = r.origin
                   AND boarding.is_boarding_allowed = TRUE
                JOIN route_stops dropping
                    ON dropping.route_id = r.id
                   AND dropping.stop_name = r.destination
                   AND dropping.is_dropping_allowed = TRUE
                   AND boarding.sequence_number < dropping.sequence_number
                WHERE s.status = 'SCHEDULED'
                ORDER BY s.travel_date
                LIMIT 1
                """
            )
        ).mappings().first()
        if schedule is None:
            pytest.skip("No scheduled route with valid origin and destination stops.")

        route_stops = connection.execute(
            text(
                """
                SELECT rs.id, rs.sequence_number
                FROM schedule_stops ss
                JOIN route_stops rs ON rs.id = ss.route_stop_id
                WHERE ss.schedule_id = :schedule_id
                ORDER BY rs.sequence_number
                """
            ),
            {"schedule_id": schedule["schedule_id"]},
        ).mappings().all()
        if len(route_stops) < 2 or (
            str(route_stops[0]["id"]) != str(schedule["boarding_stop_id"])
            or str(route_stops[-1]["id"]) != str(schedule["dropping_stop_id"])
        ):
            pytest.skip("The selected route endpoints are not its first and last stops.")
        seat_id = connection.execute(
            text(
                """
                SELECT id
                FROM bus_seats
                WHERE bus_id = :bus_id AND is_active = TRUE
                ORDER BY seat_number
                LIMIT 1
                """
            ),
            {"bus_id": schedule["bus_id"]},
        ).scalar_one_or_none()
        if seat_id is None:
            pytest.skip("The selected schedule has no route segment or active seat.")

        for index, stop in enumerate(route_stops):
            if index == 0:
                arrival_time, departure_time = "22:00", "22:15"
            elif index == len(route_stops) - 1:
                arrival_time, departure_time = "01:00", "01:05"
            else:
                arrival = datetime(2026, 10, 26, 22, 20) + timedelta(
                    minutes=index * 5
                )
                departure = arrival + timedelta(minutes=1)
                arrival_time = arrival.strftime("%H:%M")
                departure_time = departure.strftime("%H:%M")
            connection.execute(
                text(
                    """
                    UPDATE schedule_stops
                    SET arrival_time = :arrival_time,
                        departure_time = :departure_time
                    WHERE schedule_id = :schedule_id
                      AND route_stop_id = :route_stop_id
                    """
                ),
                {
                    "arrival_time": arrival_time,
                    "departure_time": departure_time,
                    "schedule_id": schedule["schedule_id"],
                    "route_stop_id": stop["id"],
                },
            )

        booking_id = uuid4()
        connection.execute(
            text(
                """
                INSERT INTO bookings (
                    id, booking_reference, auth_user_id, schedule_id,
                    boarding_stop_id, dropping_stop_id, passenger_count,
                    total_amount, status
                ) VALUES (
                    :id, :booking_reference, :auth_user_id, :schedule_id,
                    :boarding_stop_id, :dropping_stop_id, 1, 100, 'CONFIRMED'
                )
                """
            ),
            {
                "id": booking_id,
                "booking_reference": f"TICKET-TIME-{uuid4().hex}",
                "auth_user_id": uuid4(),
                "schedule_id": schedule["schedule_id"],
                "boarding_stop_id": schedule["boarding_stop_id"],
                "dropping_stop_id": schedule["dropping_stop_id"],
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO booking_seats (
                    booking_id, seat_id, passenger_name, passenger_age,
                    passenger_gender, fare
                ) VALUES (
                    :booking_id, :seat_id, 'Ticket Test', 30, 'OTHER', 100
                )
                """
            ),
            {"booking_id": booking_id, "seat_id": seat_id},
        )

        ticket = main_module._get_confirmed_ticket_details(UUID(str(booking_id)))

        assert ticket is not None
        assert ticket["boarding_time"] == "22:15:00"
        assert ticket["boarding_day_offset"] == 0
        assert ticket["dropping_time"] == "01:00:00"
        assert ticket["dropping_day_offset"] == 1
    finally:
        transaction.rollback()
        connection.close()
