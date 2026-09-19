from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine


class CheckSeatAvailabilityInput(BaseModel):
    schedule_id: UUID
    boarding_stop_id: UUID
    dropping_stop_id: UUID


class InvalidJourneySegmentError(ValueError):
    pass


VALIDATE_JOURNEY_SEGMENT_SQL = """
SELECT
    boarding.sequence_number AS boarding_sequence,
    dropping.sequence_number AS dropping_sequence,

    boarding_schedule_stop.is_boarding_allowed
        AS boarding_allowed,

    dropping_schedule_stop.is_dropping_allowed
        AS dropping_allowed

FROM schedules s

JOIN schedule_stops boarding_schedule_stop
    ON boarding_schedule_stop.schedule_id = s.id

JOIN route_stops boarding
    ON boarding.id = boarding_schedule_stop.route_stop_id

JOIN schedule_stops dropping_schedule_stop
    ON dropping_schedule_stop.schedule_id = s.id

JOIN route_stops dropping
    ON dropping.id = dropping_schedule_stop.route_stop_id

WHERE
    s.id = :schedule_id
    AND boarding.id = :boarding_stop_id
    AND dropping.id = :dropping_stop_id;
"""


CHECK_SEAT_AVAILABILITY_SQL = """
SELECT
    bs.id AS seat_id,
    bs.seat_number,
    bs.seat_type,
    bs.row_number,
    bs.column_number

FROM schedules s

JOIN buses b
    ON s.bus_id = b.id

JOIN bus_seats bs
    ON bs.bus_id = b.id

WHERE
    s.id = :schedule_id
    AND bs.is_active = TRUE

    AND NOT EXISTS (
        SELECT 1
        FROM booking_seats bks

        JOIN bookings bk
            ON bks.booking_id = bk.id

        JOIN route_stops existing_boarding
            ON bk.boarding_stop_id = existing_boarding.id

        JOIN route_stops existing_dropping
            ON bk.dropping_stop_id = existing_dropping.id

        JOIN route_stops requested_boarding
            ON requested_boarding.id = :boarding_stop_id

        JOIN route_stops requested_dropping
            ON requested_dropping.id = :dropping_stop_id

        WHERE
            bks.seat_id = bs.id
            AND bk.schedule_id = s.id
            AND bk.status = 'CONFIRMED'

            AND existing_boarding.sequence_number
                < requested_dropping.sequence_number

            AND existing_dropping.sequence_number
                > requested_boarding.sequence_number
    )

ORDER BY
    bs.row_number,
    bs.column_number,
    bs.seat_number;
"""


def validate_journey_segment(
    request: CheckSeatAvailabilityInput,
) -> None:
    with engine.connect() as connection:
        result = connection.execute(
            text(VALIDATE_JOURNEY_SEGMENT_SQL),
            {
                "schedule_id": request.schedule_id,
                "boarding_stop_id": request.boarding_stop_id,
                "dropping_stop_id": request.dropping_stop_id,
            },
        )

        row = result.fetchone()

        if row is None:
            raise InvalidJourneySegmentError(
                "Boarding and dropping stops must belong to the scheduled route."
            )

        if not row.boarding_allowed:
            raise InvalidJourneySegmentError(
                "Boarding is not allowed at the selected boarding stop."
            )

        if not row.dropping_allowed:
            raise InvalidJourneySegmentError(
                "Dropping is not allowed at the selected dropping stop."
            )

        if row.boarding_sequence >= row.dropping_sequence:
            raise InvalidJourneySegmentError(
                "Boarding stop must occur before the dropping stop."
            )


def check_seat_availability(
    request: CheckSeatAvailabilityInput,
) -> list[dict]:
    validate_journey_segment(request)

    with engine.connect() as connection:
        result = connection.execute(
            text(CHECK_SEAT_AVAILABILITY_SQL),
            {
                "schedule_id": request.schedule_id,
                "boarding_stop_id": request.boarding_stop_id,
                "dropping_stop_id": request.dropping_stop_id,
            },
        )

        return [dict(row._mapping) for row in result]