from uuid import UUID

from pydantic import BaseModel


class CreateHoldRequest(BaseModel):
    schedule_id: UUID
    seat_id: UUID
    boarding_stop_id: UUID
    dropping_stop_id: UUID