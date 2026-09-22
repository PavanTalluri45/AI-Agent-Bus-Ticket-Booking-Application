from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine


# ============================================================
# Exceptions
# ============================================================


class BookingError(Exception):
    """Base exception for booking service failures."""


class BookingNotFoundError(BookingError):
    """Raised when the requested booking does not exist."""


class BookingOwnershipError(BookingError):
    """Raised when a booking does not belong to the authenticated user."""


class HoldNotFoundError(BookingError):
    """Raised when the requested hold does not exist."""


class HoldOwnershipError(BookingError):
    """Raised when the hold does not belong to the authenticated user."""


class HoldExpiredError(BookingError):
    """Raised when the hold has expired."""


class HoldNotActiveError(BookingError):
    """Raised when the hold is not active."""


class ScheduleUnavailableError(BookingError):
    """Raised when the schedule is no longer available."""


class BookingCreationError(BookingError):
    """Raised when booking creation cannot be completed."""


# ============================================================
# SQL: Load and validate the hold
# ============================================================


CREATE_BOOKING_FROM_HOLD_SQL = """
SELECT
    h.id AS hold_id,
    h.auth_user_id,
    h.schedule_id,
    h.seat_id,
    h.boarding_stop_id,
    h.dropping_stop_id,
    h.boarding_sequence,
    h.dropping_sequence,
    h.status AS hold_status,
    h.expires_at,

    s.status AS schedule_status,
    s.bus_id,
    s.route_id,

    bs.seat_number,
    bs.is_active AS seat_active,

    fare.amount AS fare_amount,
    fare.currency AS fare_currency

FROM seat_holds h

JOIN schedules s
    ON s.id = h.schedule_id

JOIN bus_seats bs
    ON bs.id = h.seat_id

LEFT JOIN fares fare
    ON fare.schedule_id = h.schedule_id
    AND fare.boarding_stop_id = h.boarding_stop_id
    AND fare.dropping_stop_id = h.dropping_stop_id
    AND fare.is_active = TRUE

WHERE
    h.id = :hold_id

FOR UPDATE OF h;
"""


# ============================================================
# SQL: Revalidate confirmed booking conflicts
# ============================================================


REVALIDATE_CONFIRMED_BOOKING_SQL = """
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

LIMIT 1;
"""


# ============================================================
# SQL: Create payment-pending booking
# ============================================================


CREATE_BOOKING_SQL = """
INSERT INTO bookings (
    id,
    booking_reference,
    auth_user_id,
    schedule_id,
    boarding_stop_id,
    dropping_stop_id,
    passenger_count,
    total_amount,
    status
)

VALUES (
    :booking_id,
    :booking_reference,
    :auth_user_id,
    :schedule_id,
    :boarding_stop_id,
    :dropping_stop_id,
    :passenger_count,
    :total_amount,
    'PAYMENT_PENDING'
)

RETURNING
    id,
    booking_reference,
    auth_user_id,
    schedule_id,
    boarding_stop_id,
    dropping_stop_id,
    passenger_count,
    total_amount,
    status,
    booked_at,
    cancelled_at,
    created_at;
"""


# ============================================================
# SQL: Create booking seat
# ============================================================


CREATE_BOOKING_SEAT_SQL = """
INSERT INTO booking_seats (
    id,
    booking_id,
    seat_id,
    passenger_name,
    passenger_age,
    passenger_gender,
    fare
)

VALUES (
    :booking_seat_id,
    :booking_id,
    :seat_id,
    :passenger_name,
    :passenger_age,
    :passenger_gender,
    :seat_fare
)

RETURNING
    id,
    booking_id,
    seat_id,
    passenger_name,
    passenger_age,
    passenger_gender,
    fare,
    created_at;
"""


# ============================================================
# Booking reference
# ============================================================


def _generate_booking_reference() -> str:
    """
    Generate a unique booking reference.

    The database unique constraint remains the final
    authority for uniqueness.
    """

    return f"BUS-{uuid4().hex[:10].upper()}"


# ============================================================
# Create PAYMENT_PENDING booking
# ============================================================


def create_payment_pending_booking(
    current_user: AuthenticatedUser,
    hold_id: UUID,
    passenger_name: str,
    passenger_age: int,
    passenger_gender: str,
) -> dict:
    """
    Create a PAYMENT_PENDING booking from an active seat hold.

    Important rules:

    - The authenticated user's ID comes from Supabase Auth.
    - The hold must belong to the authenticated user.
    - The hold must still be active.
    - The hold must not be expired.
    - The schedule must still be scheduled.
    - The seat must still be active.
    - Confirmed booking conflicts are revalidated.
    - Fare is retrieved from the database.
    - Booking amount is calculated server-side.
    - Booking and booking_seat are created in one transaction.
    - The hold remains ACTIVE until payment succeeds.
    """

    with engine.begin() as connection:

        # ----------------------------------------------------
        # 1. Load the hold and related booking information
        # ----------------------------------------------------

        hold_result = connection.execute(
            text(CREATE_BOOKING_FROM_HOLD_SQL),
            {
                "hold_id": hold_id,
            },
        )

        hold = hold_result.mappings().first()

        if hold is None:
            raise HoldNotFoundError(
                "The requested hold was not found."
            )

        # ----------------------------------------------------
        # 2. Verify hold ownership
        # ----------------------------------------------------

        if hold["auth_user_id"] != current_user.id:
            raise HoldOwnershipError(
                "The requested hold does not belong "
                "to the authenticated user."
            )

        # ----------------------------------------------------
        # 3. Verify hold status
        # ----------------------------------------------------

        if hold["hold_status"] != "ACTIVE":
            raise HoldNotActiveError(
                "The hold is no longer active."
            )

        # ----------------------------------------------------
        # 4. Verify hold expiration
        # ----------------------------------------------------

        current_database_time = connection.execute(
            text("SELECT CURRENT_TIMESTAMP")
        ).scalar_one()

        if hold["expires_at"] <= current_database_time:
            raise HoldExpiredError(
                "The hold has expired."
            )

        # ----------------------------------------------------
        # 5. Verify schedule status
        # ----------------------------------------------------

        if hold["schedule_status"] != "SCHEDULED":
            raise ScheduleUnavailableError(
                "The scheduled journey is no longer "
                "available for booking."
            )

        # ----------------------------------------------------
        # 6. Verify seat status
        # ----------------------------------------------------

        if not hold["seat_active"]:
            raise BookingCreationError(
                "The selected seat is no longer active."
            )

        # ----------------------------------------------------
        # 7. Revalidate confirmed booking conflicts
        # ----------------------------------------------------

        conflicting_booking = connection.execute(
            text(REVALIDATE_CONFIRMED_BOOKING_SQL),
            {
                "schedule_id": hold["schedule_id"],
                "seat_id": hold["seat_id"],
                "boarding_sequence": hold["boarding_sequence"],
                "dropping_sequence": hold["dropping_sequence"],
            },
        ).first()

        if conflicting_booking is not None:
            raise BookingCreationError(
                "The selected seat is no longer available "
                "for this journey segment."
            )

        # ----------------------------------------------------
        # 8. Verify fare exists
        # ----------------------------------------------------

        if hold["fare_amount"] is None:
            raise BookingCreationError(
                "No active fare exists for the selected "
                "journey segment."
            )

        # ----------------------------------------------------
        # 9. Verify currency
        # ----------------------------------------------------

        if hold["fare_currency"] != "INR":
            raise BookingCreationError(
                "Unsupported fare currency."
            )

        # ----------------------------------------------------
        # 10. Calculate booking amount server-side
        # ----------------------------------------------------

        total_amount = Decimal(
            str(hold["fare_amount"])
        )

        # ----------------------------------------------------
        # 11. Generate booking identifiers
        # ----------------------------------------------------

        booking_id = uuid4()

        booking_reference = _generate_booking_reference()

        # ----------------------------------------------------
        # 12. Create PAYMENT_PENDING booking
        # ----------------------------------------------------

        booking_result = connection.execute(
            text(CREATE_BOOKING_SQL),
            {
                "booking_id": booking_id,
                "booking_reference": booking_reference,
                "auth_user_id": current_user.id,
                "schedule_id": hold["schedule_id"],
                "boarding_stop_id": hold["boarding_stop_id"],
                "dropping_stop_id": hold["dropping_stop_id"],
                "passenger_count": 1,
                "total_amount": total_amount,
            },
        )

        booking = booking_result.mappings().one()

        # ----------------------------------------------------
        # 13. Create booking seat
        # ----------------------------------------------------

        booking_seat_result = connection.execute(
            text(CREATE_BOOKING_SEAT_SQL),
            {
                "booking_seat_id": uuid4(),
                "booking_id": booking_id,
                "seat_id": hold["seat_id"],
                "passenger_name": passenger_name,
                "passenger_age": passenger_age,
                "passenger_gender": passenger_gender,
                "seat_fare": total_amount,
            },
        )

        booking_seat = booking_seat_result.mappings().one()

        # ----------------------------------------------------
        # 14. Return booking information
        # ----------------------------------------------------

        return {
            "booking": dict(booking),
            "booking_seat": dict(booking_seat),
        }