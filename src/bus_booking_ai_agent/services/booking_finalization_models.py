from uuid import UUID

from sqlalchemy import text

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine


# ============================================================
# Exceptions
# ============================================================


class BookingFinalizationError(Exception):
    """Base exception for booking finalization errors."""


class FinalizationPaymentNotFoundError(BookingFinalizationError):
    """Raised when the payment does not exist."""


class FinalizationPaymentOwnershipError(BookingFinalizationError):
    """Raised when the payment does not belong to the user."""


class FinalizationPaymentNotSuccessfulError(BookingFinalizationError):
    """Raised when the payment is not SUCCESS."""


class FinalizationBookingNotFoundError(BookingFinalizationError):
    """Raised when the booking does not exist."""


class FinalizationBookingStatusError(BookingFinalizationError):
    """Raised when the booking cannot be finalized."""


class FinalizationHoldNotFoundError(BookingFinalizationError):
    """Raised when the booking has no associated hold."""


class FinalizationHoldExpiredError(BookingFinalizationError):
    """Raised when the hold has expired."""


class FinalizationHoldNotActiveError(BookingFinalizationError):
    """Raised when the hold is not ACTIVE."""


class FinalizationSeatUnavailableError(BookingFinalizationError):
    """Raised when the held seat is no longer available."""


# ============================================================
# SQL: Load payment + booking
# ============================================================


GET_PAYMENT_FOR_FINALIZATION_SQL = """
SELECT
    p.id AS payment_id,
    p.booking_id,
    p.status AS payment_status,

    b.auth_user_id,
    b.status AS booking_status,
    b.schedule_id,
    b.boarding_stop_id,
    b.dropping_stop_id

FROM payments p

JOIN bookings b
    ON b.id = p.booking_id

WHERE p.id = :payment_id

FOR UPDATE OF p, b;
"""


# ============================================================
# SQL: Load active hold
# ============================================================


GET_ACTIVE_HOLD_SQL = """
SELECT
    h.id,
    h.auth_user_id,
    h.schedule_id,
    h.seat_id,
    h.boarding_stop_id,
    h.dropping_stop_id,
    h.boarding_sequence,
    h.dropping_sequence,
    h.status,
    h.expires_at

FROM seat_holds h

WHERE
    h.auth_user_id = :auth_user_id
    AND h.schedule_id = :schedule_id
    AND h.seat_id = :seat_id
    AND h.boarding_stop_id = :boarding_stop_id
    AND h.dropping_stop_id = :dropping_stop_id
    AND h.status = 'ACTIVE'

ORDER BY h.created_at DESC

LIMIT 1

FOR UPDATE;
"""


# ============================================================
# SQL: Load booking seat
# ============================================================


GET_BOOKING_SEAT_SQL = """
SELECT
    bs.id,
    bs.seat_id

FROM booking_seats bs

WHERE bs.booking_id = :booking_id

FOR UPDATE;
"""


# ============================================================
# SQL: Confirm booking
# ============================================================


CONFIRM_BOOKING_SQL = """
UPDATE bookings

SET
    status = 'CONFIRMED'

WHERE
    id = :booking_id
    AND status = 'PAYMENT_PENDING'

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
# SQL: Convert hold
# ============================================================


CONVERT_HOLD_SQL = """
UPDATE seat_holds

SET
    status = 'CONVERTED',
    converted_at = CURRENT_TIMESTAMP,
    booking_id = :booking_id

WHERE
    id = :hold_id
    AND status = 'ACTIVE'

RETURNING
    id,
    status,
    booking_id,
    converted_at;
"""


# ============================================================
# Finalize booking
# ============================================================


def finalize_booking(
    current_user: AuthenticatedUser,
    payment_id: UUID,
) -> dict:
    """
    Finalize a booking after successful payment.

    The transaction:

    1. Locks the payment and booking.
    2. Verifies payment SUCCESS.
    3. Verifies booking ownership.
    4. Verifies booking PAYMENT_PENDING.
    5. Loads the booking seat.
    6. Loads and locks the corresponding active hold.
    7. Verifies the hold has not expired.
    8. Confirms the booking.
    9. Converts the hold.

    Booking confirmation and hold conversion happen
    inside the same database transaction.
    """

    with engine.begin() as connection:

        # --------------------------------------------------------
        # 1. Load and lock payment + booking
        # --------------------------------------------------------

        payment_result = connection.execute(
            text(GET_PAYMENT_FOR_FINALIZATION_SQL),
            {
                "payment_id": payment_id,
            },
        )

        payment = payment_result.mappings().first()

        if payment is None:
            raise FinalizationPaymentNotFoundError(
                "The requested payment was not found."
            )

        # --------------------------------------------------------
        # 2. Verify ownership
        # --------------------------------------------------------

        if payment["auth_user_id"] != current_user.id:
            raise FinalizationPaymentOwnershipError(
                "The payment does not belong to the authenticated user."
            )

        # --------------------------------------------------------
        # 3. Verify payment status
        # --------------------------------------------------------

        if payment["payment_status"] != "SUCCESS":
            raise FinalizationPaymentNotSuccessfulError(
                "The payment has not been successfully verified."
            )

        # --------------------------------------------------------
        # 4. Verify booking status
        # --------------------------------------------------------

        if payment["booking_status"] != "PAYMENT_PENDING":
            raise FinalizationBookingStatusError(
                "The booking is not waiting for payment finalization."
            )

        booking_id = payment["booking_id"]

        # --------------------------------------------------------
        # 5. Load booking seat
        # --------------------------------------------------------

        booking_seat_result = connection.execute(
            text(GET_BOOKING_SEAT_SQL),
            {
                "booking_id": booking_id,
            },
        )

        booking_seat = booking_seat_result.mappings().first()

        if booking_seat is None:
            raise FinalizationSeatUnavailableError(
                "The booking does not contain a reserved seat."
            )

        seat_id = booking_seat["seat_id"]

        # --------------------------------------------------------
        # 6. Load and lock active hold
        # --------------------------------------------------------

        hold_result = connection.execute(
            text(GET_ACTIVE_HOLD_SQL),
            {
                "auth_user_id": payment["auth_user_id"],
                "schedule_id": payment["schedule_id"],
                "seat_id": seat_id,
                "boarding_stop_id": payment["boarding_stop_id"],
                "dropping_stop_id": payment["dropping_stop_id"],
            },
        )

        hold = hold_result.mappings().first()

        if hold is None:
            raise FinalizationHoldNotFoundError(
                "The active seat hold could not be found."
            )

        # --------------------------------------------------------
        # 7. Verify hold status
        # --------------------------------------------------------

        if hold["status"] != "ACTIVE":
            raise FinalizationHoldNotActiveError(
                "The seat hold is no longer active."
            )

        # --------------------------------------------------------
        # 8. Verify hold expiration
        # --------------------------------------------------------

        expiration_result = connection.execute(
            text(
                """
                SELECT CURRENT_TIMESTAMP < :expires_at
                AS is_valid;
                """
            ),
            {
                "expires_at": hold["expires_at"],
            },
        )

        expiration = expiration_result.scalar_one()

        if not expiration:
            raise FinalizationHoldExpiredError(
                "The seat hold has expired."
            )

        # --------------------------------------------------------
        # 9. Confirm booking
        # --------------------------------------------------------

        booking_update_result = connection.execute(
            text(CONFIRM_BOOKING_SQL),
            {
                "booking_id": booking_id,
            },
        )

        confirmed_booking = (
            booking_update_result.mappings().first()
        )

        if confirmed_booking is None:
            raise FinalizationBookingStatusError(
                "The booking could not be confirmed."
            )

        # --------------------------------------------------------
        # 10. Convert hold
        # --------------------------------------------------------

        hold_update_result = connection.execute(
            text(CONVERT_HOLD_SQL),
            {
                "hold_id": hold["id"],
                "booking_id": booking_id,
            },
        )

        converted_hold = (
            hold_update_result.mappings().first()
        )

        if converted_hold is None:
            raise FinalizationHoldNotActiveError(
                "The hold could not be converted."
            )

        # --------------------------------------------------------
        # 11. Return finalized result
        # --------------------------------------------------------

        return {
            "booking": dict(confirmed_booking),
            "hold": dict(converted_hold),
            "payment_id": payment_id,
        }