from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class Payment(BaseModel):
    """
    Represents a payment tracked by the application.

    The payment provider is an external system.
    This model represents the payment information
    maintained by our application.
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
    The backend determines the amount, currency,
    authenticated user, and payment state.
    """

    booking_id: UUID