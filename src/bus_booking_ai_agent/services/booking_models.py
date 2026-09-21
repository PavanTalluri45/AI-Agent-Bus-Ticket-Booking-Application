from uuid import UUID

from pydantic import BaseModel


class ConfirmBookingRequest(BaseModel):
    """
    Request to convert an existing seat hold
    into a confirmed booking.
    """

    hold_id: UUID