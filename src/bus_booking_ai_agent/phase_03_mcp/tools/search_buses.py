from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine


class SearchBusesInput(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    travel_date: date


SEARCH_BUSES_SQL = """
SELECT
    s.id AS schedule_id,
    s.travel_date,

    b.id AS bus_id,
    b.bus_number,
    b.bus_type,
    b.total_seats,

    o.id AS operator_id,
    o.name AS operator_name,

    r.id AS route_id,
    r.origin,
    r.destination

FROM schedules s

JOIN buses b
    ON s.bus_id = b.id

JOIN operators o
    ON b.operator_id = o.id

JOIN routes r
    ON s.route_id = r.id

WHERE
    r.origin = :origin
    AND r.destination = :destination
    AND s.travel_date = :travel_date
    AND s.status = 'SCHEDULED'
    AND b.is_active = TRUE
    AND o.is_active = TRUE
    AND r.is_active = TRUE

ORDER BY
    s.travel_date,
    b.bus_number;
"""


def search_buses(request: SearchBusesInput) -> list[dict]:
    with engine.connect() as connection:
        result = connection.execute(
            text(SEARCH_BUSES_SQL),
            {
                "origin": request.origin,
                "destination": request.destination,
                "travel_date": request.travel_date,
            },
        )

        return [dict(row._mapping) for row in result]