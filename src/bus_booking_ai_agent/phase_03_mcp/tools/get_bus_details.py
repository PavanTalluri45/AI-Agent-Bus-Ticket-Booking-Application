from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine


class GetBusDetailsInput(BaseModel):
    schedule_id: UUID


GET_BUS_DETAILS_SQL = """
SELECT
    s.id AS schedule_id,
    s.travel_date,
    s.status,

    b.id AS bus_id,
    b.bus_number,
    b.bus_type,
    b.total_seats,

    o.id AS operator_id,
    o.name AS operator_name,
    o.contact_phone,
    o.email,

    r.id AS route_id,
    r.origin,
    r.destination,
    r.distance_km,
    r.estimated_duration_minutes

FROM schedules s

JOIN buses b
    ON s.bus_id = b.id

JOIN operators o
    ON b.operator_id = o.id

JOIN routes r
    ON s.route_id = r.id

WHERE
    s.id = :schedule_id;
"""


def get_bus_details(request: GetBusDetailsInput) -> dict | None:
    with engine.connect() as connection:
        result = connection.execute(
            text(GET_BUS_DETAILS_SQL),
            {
                "schedule_id": request.schedule_id,
            },
        )

        row = result.fetchone()

        if row is None:
            return None

        return dict(row._mapping)