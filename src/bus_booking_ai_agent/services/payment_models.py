from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class Payment(BaseModel):
    """
    Represents a payment tracked by the application.
    """

    id: UUID
    booking_id: UUID

    provider: str
    provider_order_id: str
    provider_payment_id: str | None = None

    amount: Decimal = Field(gt=0)
    currency: str = "INR"

    status: str

    created_at: str
    paid_at: str | None = None


class CreatePaymentRequest(BaseModel):
    """
    Request to initiate payment for an existing booking.

    The client provides only the booking ID.

    The backend determines:
    - amount
    - currency
    - authenticated user
    - payment state
    """

    booking_id: UUID


class VerifyPaymentRequest(BaseModel):
    """
    Razorpay payment verification request.

    The frontend sends the values returned by Razorpay.
    The backend verifies them against the stored payment
    and the Razorpay signature.
    """

    payment_id: UUID

    razorpay_payment_id: str = Field(
        min_length=1
    )

    razorpay_order_id: str = Field(
        min_length=1
    )

    razorpay_signature: str = Field(
        min_length=1
    )