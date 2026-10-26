from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_03_mcp.tools.check_seat_availability import (
    CHECK_SEAT_AVAILABILITY_SQL,
)


TEST_USER_ID = "7803ebf4-7421-495d-b186-ec01c7c591c3"


def test_availability_marks_confirmed_and_active_overlaps_unavailable():
    try:
        connection = engine.connect()
    except SQLAlchemyError as error:
        pytest.skip(f"PostgreSQL test database is unavailable: {error}")

    with connection:
        transaction = connection.begin()
        try:
            stop_rows = connection.execute(
                text(
                    """
                    SELECT ss.schedule_id, rs.id, rs.sequence_number
                    FROM schedule_stops ss
                    JOIN route_stops rs ON rs.id = ss.route_stop_id
                    ORDER BY ss.schedule_id, rs.sequence_number
                    """
                )
            ).mappings().all()
            stops_by_schedule = {}
            for row in stop_rows:
                stops_by_schedule.setdefault(str(row["schedule_id"]), []).append(row)

            test_segment = None
            for schedule_id, route_stops in stops_by_schedule.items():
                if len(route_stops) < 3:
                    continue

                requested_boarding, requested_dropping, adjacent_stop = route_stops[:3]
                parameters = {
                    "schedule_id": schedule_id,
                    "boarding_stop_id": str(requested_boarding["id"]),
                    "dropping_stop_id": str(requested_dropping["id"]),
                }
                initial_rows = connection.execute(
                    text(CHECK_SEAT_AVAILABILITY_SQL),
                    parameters,
                ).mappings().all()
                available_seats = [
                    row for row in initial_rows if row["status"] == "available"
                ]
                if len(available_seats) >= 4:
                    test_segment = (
                        schedule_id,
                        requested_boarding,
                        requested_dropping,
                        adjacent_stop,
                        available_seats,
                    )
                    break

            if test_segment is None:
                pytest.skip("No schedule has a segment and four initially available seats.")

            (
                schedule_id,
                requested_boarding,
                requested_dropping,
                adjacent_stop,
                available_seats,
            ) = test_segment
            boarding_stop_id = str(requested_boarding["id"])
            dropping_stop_id = str(requested_dropping["id"])
            boarding_sequence = requested_boarding["sequence_number"]
            dropping_sequence = requested_dropping["sequence_number"]
            parameters = {
                "schedule_id": schedule_id,
                "boarding_stop_id": boarding_stop_id,
                "dropping_stop_id": dropping_stop_id,
            }
            confirmed_seat, active_seat, expired_seat, adjacent_seat = available_seats[:4]

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
                    "booking_reference": f"SEATMAP-{uuid4()}",
                    "auth_user_id": TEST_USER_ID,
                    "schedule_id": schedule_id,
                    "boarding_stop_id": boarding_stop_id,
                    "dropping_stop_id": dropping_stop_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO booking_seats (
                        booking_id, seat_id, passenger_name, passenger_age,
                        passenger_gender, fare
                    ) VALUES (
                        :booking_id, :seat_id, 'Seat Map Test', 30, 'OTHER', 1
                    )
                    """
                ),
                {"booking_id": booking_id, "seat_id": confirmed_seat["seat_id"]},
            )

            now = datetime.now(timezone.utc)
            hold_values = [
                {
                    "seat_id": active_seat["seat_id"],
                    "boarding_stop_id": boarding_stop_id,
                    "dropping_stop_id": dropping_stop_id,
                    "boarding_sequence": boarding_sequence,
                    "dropping_sequence": dropping_sequence,
                    "created_at": now - timedelta(minutes=1),
                    "expires_at": now + timedelta(minutes=10),
                },
                {
                    "seat_id": expired_seat["seat_id"],
                    "boarding_stop_id": boarding_stop_id,
                    "dropping_stop_id": dropping_stop_id,
                    "boarding_sequence": boarding_sequence,
                    "dropping_sequence": dropping_sequence,
                    "created_at": now - timedelta(minutes=10),
                    "expires_at": now - timedelta(minutes=1),
                },
                {
                    "seat_id": adjacent_seat["seat_id"],
                    "boarding_stop_id": dropping_stop_id,
                    "dropping_stop_id": str(adjacent_stop["id"]),
                    "boarding_sequence": dropping_sequence,
                    "dropping_sequence": adjacent_stop["sequence_number"],
                    "created_at": now - timedelta(minutes=1),
                    "expires_at": now + timedelta(minutes=10),
                },
            ]
            for hold in hold_values:
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
                        **hold,
                        "auth_user_id": TEST_USER_ID,
                        "schedule_id": schedule_id,
                    },
                )

            result_rows = connection.execute(
                text(CHECK_SEAT_AVAILABILITY_SQL),
                parameters,
            ).mappings().all()
            status_by_seat_id = {
                str(row["seat_id"]): row["status"] for row in result_rows
            }
            assert status_by_seat_id[str(confirmed_seat["seat_id"])] == "unavailable"
            assert status_by_seat_id[str(active_seat["seat_id"])] == "unavailable"
            assert status_by_seat_id[str(expired_seat["seat_id"])] == "available"
            assert status_by_seat_id[str(adjacent_seat["seat_id"])] == "available"
        finally:
            transaction.rollback()
