from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine


HOLD_DURATION_MINUTES = 10


class HoldError(Exception):
    """Base exception for hold creation failures."""


class ScheduleNotFoundError(HoldError):
    pass


class ScheduleUnavailableError(HoldError):
    pass


class SeatNotAvailableError(HoldError):
    pass


class InvalidJourneySegmentError(HoldError):
    pass


class HoldConflictError(HoldError):
    pass


CREATE_HOLD_SQL = """
WITH schedule_data AS (
    SELECT
        s.id AS schedule_id,
        s.bus_id,
        s.route_id,
        s.status
    FROM schedules s
    WHERE s.id = :schedule_id
)

SELECT
    s.schedule_id,
    s.bus_id,
    s.route_id,
    s.status,

    boarding.route_stop_id AS boarding_stop_id,
    boarding_stop.sequence_number AS boarding_sequence,
    boarding.is_boarding_allowed,

    dropping.route_stop_id AS dropping_stop_id,
    dropping_stop.sequence_number AS dropping_sequence,
    dropping.is_dropping_allowed

FROM schedule_data s

LEFT JOIN schedule_stops boarding
    ON boarding.schedule_id = s.schedule_id
    AND boarding.route_stop_id = :boarding_stop_id

LEFT JOIN route_stops boarding_stop
    ON boarding_stop.id = boarding.route_stop_id

LEFT JOIN schedule_stops dropping
    ON dropping.schedule_id = s.schedule_id
    AND dropping.route_stop_id = :dropping_stop_id

LEFT JOIN route_stops dropping_stop
    ON dropping_stop.id = dropping.route_stop_id;
"""


def _validate_schedule_and_journey(
    connection,
    schedule_id: UUID,
    seat_id: UUID,
    boarding_stop_id: UUID,
    dropping_stop_id: UUID,
) -> dict:
    """
    Validate the selected schedule, seat, and journey segment.

    Stop membership and boarding/dropping permissions are validated
    against schedule_stops because these rules belong to the specific
    scheduled journey.
    """

    result = connection.execute(
        text(CREATE_HOLD_SQL),
        {
            "schedule_id": schedule_id,
            "boarding_stop_id": boarding_stop_id,
            "dropping_stop_id": dropping_stop_id,
        },
    ).mappings().first()

    # ------------------------------------------------------
    # 1. Schedule existence
    # ------------------------------------------------------

    if result is None:
        raise ScheduleNotFoundError(
            "The selected schedule does not exist."
        )

    # ------------------------------------------------------
    # 2. Schedule status
    # ------------------------------------------------------

    if result["status"] != "SCHEDULED":
        raise ScheduleUnavailableError(
            "The selected schedule is not available for booking."
        )

    # ------------------------------------------------------
    # 3. Boarding stop belongs to this schedule
    # ------------------------------------------------------

    if result["boarding_stop_id"] is None:
        raise InvalidJourneySegmentError(
            "Boarding stop does not belong to the selected schedule."
        )

    # ------------------------------------------------------
    # 4. Dropping stop belongs to this schedule
    # ------------------------------------------------------

    if result["dropping_stop_id"] is None:
        raise InvalidJourneySegmentError(
            "Dropping stop does not belong to the selected schedule."
        )

    # ------------------------------------------------------
    # 5. Boarding is allowed
    # ------------------------------------------------------

    if not result["is_boarding_allowed"]:
        raise InvalidJourneySegmentError(
            "Boarding is not allowed at the selected boarding stop."
        )

    # ------------------------------------------------------
    # 6. Dropping is allowed
    # ------------------------------------------------------

    if not result["is_dropping_allowed"]:
        raise InvalidJourneySegmentError(
            "Dropping is not allowed at the selected dropping stop."
        )

    # ------------------------------------------------------
    # 7. Journey direction
    # ------------------------------------------------------

    if result["boarding_sequence"] >= result["dropping_sequence"]:
        raise InvalidJourneySegmentError(
            "Boarding stop must occur before the dropping stop."
        )

    # ------------------------------------------------------
    # 8. Verify seat belongs to the scheduled bus
    # ------------------------------------------------------

    seat_result = connection.execute(
        text(
            """
            SELECT 1
            FROM bus_seats
            WHERE
                id = :seat_id
                AND bus_id = :bus_id
                AND is_active = TRUE
            """
        ),
        {
            "seat_id": seat_id,
            "bus_id": result["bus_id"],
        },
    ).first()

    if seat_result is None:
        raise SeatNotAvailableError(
            "The selected seat does not belong to the scheduled bus."
        )

    return dict(result)


def _has_confirmed_booking_conflict(
    connection,
    schedule_id: UUID,
    seat_id: UUID,
    boarding_sequence: int,
    dropping_sequence: int,
) -> bool:
    """
    Check whether the seat is already booked for an overlapping
    journey segment.

    Overlap rule:

        existing boarding < requested dropping
        AND
        existing dropping > requested boarding
    """

    result = connection.execute(
        text(
            """
            SELECT 1

            FROM booking_seats bs

            JOIN bookings b
                ON b.id = bs.booking_id

            JOIN route_stops boarding
                ON boarding.id = b.boarding_stop_id

            JOIN route_stops dropping
                ON dropping.id = b.dropping_stop_id

            WHERE
                b.schedule_id = :schedule_id
                AND bs.seat_id = :seat_id
                AND b.status = 'CONFIRMED'

                AND boarding.sequence_number < :dropping_sequence
                AND dropping.sequence_number > :boarding_sequence

            LIMIT 1
            """
        ),
        {
            "schedule_id": schedule_id,
            "seat_id": seat_id,
            "boarding_sequence": boarding_sequence,
            "dropping_sequence": dropping_sequence,
        },
    ).first()

    return result is not None


def _has_active_hold_conflict(
    connection,
    schedule_id: UUID,
    seat_id: UUID,
    boarding_sequence: int,
    dropping_sequence: int,
) -> bool:
    """
    Check whether the seat currently has an active,
    non-expired hold for an overlapping journey segment.
    """

    result = connection.execute(
        text(
            """
            SELECT 1
            FROM seat_holds

            WHERE
                schedule_id = :schedule_id
                AND seat_id = :seat_id

                AND status = 'ACTIVE'
                AND expires_at > CURRENT_TIMESTAMP

                AND boarding_sequence < :dropping_sequence
                AND dropping_sequence > :boarding_sequence

            LIMIT 1
            """
        ),
        {
            "schedule_id": schedule_id,
            "seat_id": seat_id,
            "boarding_sequence": boarding_sequence,
            "dropping_sequence": dropping_sequence,
        },
    ).first()

    return result is not None


def create_hold(
    current_user: AuthenticatedUser,
    schedule_id: UUID,
    seat_id: UUID,
    boarding_stop_id: UUID,
    dropping_stop_id: UUID,
) -> dict:
    """
    Create a temporary seat hold for the authenticated user.

    The authenticated user comes from Supabase Auth through
    AuthenticatedUser. The user ID is never accepted from the
    request body.

    All validation and creation happen inside one database
    transaction.
    """

    with engine.begin() as connection:

        # ------------------------------------------------------
        # 1. Acquire transaction-level advisory lock
        #
        # Lock the logical schedule + seat combination.
        #
        # This prevents two concurrent requests from both seeing
        # the seat as available and creating conflicting holds.
        # ------------------------------------------------------

        connection.execute(
            text(
                """
                SELECT pg_advisory_xact_lock(
                    hashtextextended(
                        CAST(:schedule_id AS TEXT)
                        || ':'
                        || CAST(:seat_id AS TEXT),
                        0
                    )
                )
                """
            ),
            {
                "schedule_id": schedule_id,
                "seat_id": seat_id,
            },
        )

        # ------------------------------------------------------
        # 2. Validate schedule, seat, and journey
        # ------------------------------------------------------

        journey = _validate_schedule_and_journey(
            connection=connection,
            schedule_id=schedule_id,
            seat_id=seat_id,
            boarding_stop_id=boarding_stop_id,
            dropping_stop_id=dropping_stop_id,
        )

        boarding_sequence = journey["boarding_sequence"]
        dropping_sequence = journey["dropping_sequence"]

        # ------------------------------------------------------
        # 3. Check confirmed booking conflicts
        # ------------------------------------------------------

        if _has_confirmed_booking_conflict(
            connection=connection,
            schedule_id=schedule_id,
            seat_id=seat_id,
            boarding_sequence=boarding_sequence,
            dropping_sequence=dropping_sequence,
        ):
            raise SeatNotAvailableError(
                "The selected seat is already booked "
                "for an overlapping journey segment."
            )

        # ------------------------------------------------------
        # 4. Check active hold conflicts
        # ------------------------------------------------------

        if _has_active_hold_conflict(
            connection=connection,
            schedule_id=schedule_id,
            seat_id=seat_id,
            boarding_sequence=boarding_sequence,
            dropping_sequence=dropping_sequence,
        ):
            raise HoldConflictError(
                "The selected seat is currently held "
                "for an overlapping journey segment."
            )

        # ------------------------------------------------------
        # 5. Calculate expiration
        # ------------------------------------------------------

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=HOLD_DURATION_MINUTES)
        )

        # ------------------------------------------------------
        # 6. Create hold
        # ------------------------------------------------------

        result = connection.execute(
            text(
                """
                INSERT INTO seat_holds (
                    auth_user_id,
                    schedule_id,
                    seat_id,
                    boarding_stop_id,
                    dropping_stop_id,
                    boarding_sequence,
                    dropping_sequence,
                    status,
                    expires_at
                )

                VALUES (
                    :auth_user_id,
                    :schedule_id,
                    :seat_id,
                    :boarding_stop_id,
                    :dropping_stop_id,
                    :boarding_sequence,
                    :dropping_sequence,
                    'ACTIVE',
                    :expires_at
                )

                RETURNING
                    id,
                    auth_user_id,
                    schedule_id,
                    seat_id,
                    boarding_stop_id,
                    dropping_stop_id,
                    boarding_sequence,
                    dropping_sequence,
                    status,
                    expires_at,
                    created_at
                """
            ),
            {
                "auth_user_id": current_user.id,
                "schedule_id": schedule_id,
                "seat_id": seat_id,
                "boarding_stop_id": boarding_stop_id,
                "dropping_stop_id": dropping_stop_id,
                "boarding_sequence": boarding_sequence,
                "dropping_sequence": dropping_sequence,
                "expires_at": expires_at,
            },
        )

        hold = result.mappings().one()

        return dict(hold)