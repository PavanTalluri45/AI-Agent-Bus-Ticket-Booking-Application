from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine


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
    """Raised when the schedule cannot be booked."""


class BookingCreationError(BookingError):
    """Raised when booking creation fails."""


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


CREATE_BOOKING_SEAT_SQL = """
INSERT INTO booking_seats (
    id,
    booking_id,
    seat_id,
    passenger_name,
    passenger_age,
    passenger_gender,
    seat_fare
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
    seat_fare,
    created_at;
"""


def _generate_booking_reference() -> str:
    """
    Generate a unique application booking reference.

    The database unique constraint remains the final authority.
    """
    return f"BUS-{uuid4().hex[:10].upper()}"


def create_payment_pending_booking(
    current_user: AuthenticatedUser,
    hold_id: UUID,
    passenger_name: str,
    passenger_age: int,
    passenger_gender: str,
) -> dict:
    """
    Create a PAYMENT_PENDING booking from an active seat hold.

    The authenticated user's UUID comes from Supabase Auth.
    Fare and booking amount come from the database.
    """

    with engine.begin() as connection:

        hold = connection.execute(
            text(CREATE_BOOKING_FROM_HOLD_SQL),
            {
                "hold_id": hold_id,
            },
        ).mappings().first()

        if hold is None:
            raise HoldNotFoundError(
                "The requested hold was not found."
            )

        if hold["auth_user_id"] != current_user.id:
            raise HoldOwnershipError(
                "The requested hold does not belong to the authenticated user."
            )

        if hold["status"] != "ACTIVE":
            raise HoldNotActiveError(
                "The hold is no longer active."
            )

        if hold["expires_at"] <= connection.execute(
            text("SELECT CURRENT_TIMESTAMP")
        ).scalar_one():
            raise HoldExpiredError(
                "The hold has expired."
            )

        if hold["schedule_status"] != "SCHEDULED":
            raise ScheduleUnavailableError(
                "The scheduled journey is no longer available for booking."
            )

        if not hold["seat_active"]:
            raise BookingCreationError(
                "The selected seat is no longer active."
            )

        if hold["fare_amount"] is None:
            raise BookingCreationError(
                "No active fare exists for the selected journey segment."
            )

        if hold["fare_currency"] != "INR":
            raise BookingCreationError(
                "Unsupported fare currency."
            )

        total_amount = Decimal(str(hold["fare_amount"]))

        booking_id = uuid4()
        booking_reference = _generate_booking_reference()

        booking = connection.execute(
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
        ).mappings().one()

        booking_seat = connection.execute(
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
        ).mappings().one()

        return {
            "booking": dict(booking),
            "booking_seat": dict(booking_seat),
        }