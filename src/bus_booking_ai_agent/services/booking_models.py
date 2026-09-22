from uuid import UUID

from pydantic import BaseModel, Field


class CreatePaymentPendingBookingRequest(BaseModel):
    """
    Request to create a payment-pending booking
    from an existing active seat hold.
    """

    hold_id: UUID
    passenger_name: str = Field(min_length=1, max_length=100)
    passenger_age: int = Field(ge=1, le=120)
    passenger_gender: str = Field(min_length=1, max_length=20)


class ConfirmBookingRequest(BaseModel):
    """
    Request used later to finalize a booking
    after successful payment.
    """

    hold_id: UUID