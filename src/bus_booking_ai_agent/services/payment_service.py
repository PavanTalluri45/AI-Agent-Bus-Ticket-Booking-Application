from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine


# ============================================================
# Exceptions
# ============================================================


class PaymentError(Exception):
    """Base exception for payment service failures."""


class PaymentBookingNotFoundError(PaymentError):
    """Raised when the booking does not exist."""


class PaymentBookingOwnershipError(PaymentError):
    """Raised when the booking does not belong to the authenticated user."""


class InvalidPaymentBookingStatusError(PaymentError):
    """Raised when the booking cannot enter payment."""


class PaymentNotFoundError(PaymentError):
    """Raised when the payment does not exist."""


class PaymentOwnershipError(PaymentError):
    """Raised when the payment does not belong to the authenticated user."""


class PaymentAlreadyProcessedError(PaymentError):
    """Raised when the payment has already been processed."""


class PaymentOrderMismatchError(PaymentError):
    """Raised when the Razorpay order does not match the application payment."""


class PaymentVerificationError(PaymentError):
    """Raised when payment verification fails."""


# ============================================================
# Payment Provider Interface
# ============================================================


class PaymentProvider(ABC):
    """
    Abstract interface for an external payment provider.

    The payment service depends on this interface instead of
    depending directly on Razorpay.
    """

    @abstractmethod
    def create_order(
        self,
        amount: Decimal,
        currency: str,
        receipt: str,
    ) -> dict:
        """
        Create a payment order with the external provider.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> None:
        """
        Verify the payment provider signature.
        """
        raise NotImplementedError


# ============================================================
# SQL: Load booking for payment
# ============================================================


GET_BOOKING_FOR_PAYMENT_SQL = """
SELECT
    id,
    booking_reference,
    auth_user_id,
    total_amount,
    status
FROM bookings
WHERE id = :booking_id;
"""


# ============================================================
# SQL: Create payment record
# ============================================================


CREATE_PAYMENT_SQL = """
INSERT INTO payments (
    id,
    booking_id,
    provider,
    provider_order_id,
    amount,
    currency,
    status
)
VALUES (
    :payment_id,
    :booking_id,
    :provider,
    :provider_order_id,
    :amount,
    :currency,
    'CREATED'
)
RETURNING
    id,
    booking_id,
    provider,
    provider_order_id,
    provider_payment_id,
    amount,
    currency,
    status,
    created_at,
    paid_at;
"""


# ============================================================
# SQL: Load payment for verification
# ============================================================


GET_PAYMENT_FOR_VERIFICATION_SQL = """
SELECT
    p.id,
    p.booking_id,
    p.provider,
    p.provider_order_id,
    p.provider_payment_id,
    p.amount,
    p.currency,
    p.status,

    b.auth_user_id,
    b.status AS booking_status

FROM payments p

JOIN bookings b
    ON b.id = p.booking_id

WHERE p.id = :payment_id

FOR UPDATE;
"""


# ============================================================
# SQL: Mark payment as successful
# ============================================================


MARK_PAYMENT_SUCCESS_SQL = """
UPDATE payments
SET
    provider_payment_id = :provider_payment_id,
    status = 'SUCCESS',
    paid_at = CURRENT_TIMESTAMP
WHERE id = :payment_id
RETURNING
    id,
    booking_id,
    provider,
    provider_order_id,
    provider_payment_id,
    amount,
    currency,
    status,
    created_at,
    paid_at;
"""


# ============================================================
# Create payment order
# ============================================================


def prepare_payment(
    current_user: AuthenticatedUser,
    booking_id: UUID,
    provider: PaymentProvider,
) -> dict:
    """
    Validate a PAYMENT_PENDING booking, create an external
    payment order, and persist the payment record.

    Important rules:

    - Booking must exist.
    - Booking must belong to the authenticated user.
    - Booking status must be PAYMENT_PENDING.
    - Amount is read from the database.
    - Frontend cannot provide or modify the payment amount.
    - Currency is determined by the backend.
    - External provider creates the actual payment order.
    - Provider order ID is persisted in the payments table.
    - Payment starts with CREATED status.
    - Booking remains PAYMENT_PENDING.
    - Booking is NOT confirmed here.
    """

    with engine.begin() as connection:

        # --------------------------------------------------------
        # 1. Load booking
        # --------------------------------------------------------

        booking_result = connection.execute(
            text(GET_BOOKING_FOR_PAYMENT_SQL),
            {
                "booking_id": booking_id,
            },
        )

        booking = booking_result.mappings().first()

        if booking is None:
            raise PaymentBookingNotFoundError(
                "The requested booking was not found."
            )

        # --------------------------------------------------------
        # 2. Verify booking ownership
        # --------------------------------------------------------

        if booking["auth_user_id"] != current_user.id:
            raise PaymentBookingOwnershipError(
                "The requested booking does not belong "
                "to the authenticated user."
            )

        # --------------------------------------------------------
        # 3. Verify booking status
        # --------------------------------------------------------

        if booking["status"] != "PAYMENT_PENDING":
            raise InvalidPaymentBookingStatusError(
                "The booking is not available for payment."
            )

        # --------------------------------------------------------
        # 4. Read amount from database
        # --------------------------------------------------------

        amount = Decimal(str(booking["total_amount"]))

        if amount <= 0:
            raise PaymentError(
                "The booking amount must be greater than zero."
            )

        # --------------------------------------------------------
        # 5. Create order with payment provider
        # --------------------------------------------------------

        provider_order = provider.create_order(
            amount=amount,
            currency="INR",
            receipt=booking["booking_reference"],
        )

        # --------------------------------------------------------
        # 6. Validate provider response
        # --------------------------------------------------------

        provider_order_id = provider_order.get("id")

        if not provider_order_id:
            raise PaymentError(
                "The payment provider did not return an order ID."
            )

        provider_amount = provider_order.get("amount")

        expected_amount_in_paise = int(amount * 100)

        if provider_amount != expected_amount_in_paise:
            raise PaymentError(
                "The payment provider returned an unexpected amount."
            )

        provider_currency = provider_order.get("currency")

        if provider_currency != "INR":
            raise PaymentError(
                "The payment provider returned an unexpected currency."
            )

        # --------------------------------------------------------
        # 7. Create application payment record
        # --------------------------------------------------------

        payment_id = uuid4()

        payment_result = connection.execute(
            text(CREATE_PAYMENT_SQL),
            {
                "payment_id": payment_id,
                "booking_id": booking["id"],
                "provider": "razorpay",
                "provider_order_id": provider_order_id,
                "amount": amount,
                "currency": "INR",
            },
        )

        payment = payment_result.mappings().one()

        # --------------------------------------------------------
        # 8. Return payment information
        # --------------------------------------------------------

        return {
            "payment": dict(payment),
            "provider_order": provider_order,
        }


# ============================================================
# Verify payment
# ============================================================


def verify_payment(
    current_user: AuthenticatedUser,
    payment_id: UUID,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
    provider: PaymentProvider,
) -> dict:
    """
    Verify a Razorpay payment signature and mark the application
    payment as SUCCESS.

    Important:

    - The payment must exist.
    - The payment must belong to the authenticated user.
    - The payment must currently be CREATED.
    - The Razorpay order ID must match our stored order ID.
    - The provider must be Razorpay.
    - The Razorpay signature must be valid.
    - Only after successful verification is the payment marked SUCCESS.

    This function does NOT confirm the booking.
    Booking finalization is a separate transaction.
    """

    with engine.begin() as connection:

        # --------------------------------------------------------
        # 1. Load payment and booking
        # --------------------------------------------------------

        payment_result = connection.execute(
            text(GET_PAYMENT_FOR_VERIFICATION_SQL),
            {
                "payment_id": payment_id,
            },
        )

        payment = payment_result.mappings().first()

        if payment is None:
            raise PaymentNotFoundError(
                "The requested payment was not found."
            )

        # --------------------------------------------------------
        # 2. Verify ownership
        # --------------------------------------------------------

        if payment["auth_user_id"] != current_user.id:
            raise PaymentOwnershipError(
                "The requested payment does not belong "
                "to the authenticated user."
            )

        # --------------------------------------------------------
        # 3. Verify payment status
        # --------------------------------------------------------

        if payment["status"] != "CREATED":
            raise PaymentAlreadyProcessedError(
                "The payment has already been processed."
            )

        # --------------------------------------------------------
        # 4. Verify provider
        # --------------------------------------------------------

        if payment["provider"] != "razorpay":
            raise PaymentVerificationError(
                "Unsupported payment provider."
            )

        # --------------------------------------------------------
        # 5. Verify Razorpay order ID
        # --------------------------------------------------------

        if payment["provider_order_id"] != razorpay_order_id:
            raise PaymentOrderMismatchError(
                "The Razorpay order does not match "
                "the application payment."
            )

        # --------------------------------------------------------
        # 6. Verify Razorpay signature
        # --------------------------------------------------------

        try:
            provider.verify_payment_signature(
                order_id=razorpay_order_id,
                payment_id=razorpay_payment_id,
                signature=razorpay_signature,
            )

        except Exception as error:
            raise PaymentVerificationError(
                "Payment signature verification failed."
            ) from error

        # --------------------------------------------------------
        # 7. Mark payment as SUCCESS
        # --------------------------------------------------------

        payment_update_result = connection.execute(
            text(MARK_PAYMENT_SUCCESS_SQL),
            {
                "payment_id": payment_id,
                "provider_payment_id": razorpay_payment_id,
            },
        )

        updated_payment = payment_update_result.mappings().one()

        # --------------------------------------------------------
        # 8. Return verified payment
        # --------------------------------------------------------

        return {
            "payment": dict(updated_payment),
            "booking_id": payment["booking_id"],
        }