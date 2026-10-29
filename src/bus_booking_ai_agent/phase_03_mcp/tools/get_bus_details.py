from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_03_mcp.tools.schedule_time_utils import (
    add_day_offsets,
    format_time_display,
)


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
    r.estimated_duration_minutes,

    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'stop_id', rs.id,
                    'sequence_number', rs.sequence_number,
                    'arrival_time', ss.arrival_time,
                    'departure_time', ss.departure_time
                )
                ORDER BY rs.sequence_number
            )
            FROM schedule_stops ss
            JOIN route_stops rs
                ON rs.id = ss.route_stop_id
            WHERE ss.schedule_id = s.id
        ),
        '[]'::jsonb
    ) AS _schedule_stops,

    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'stop_id', rs.id,
                    'stop_name', rs.stop_name,
                    'city', rs.city,
                    'sequence_number', rs.sequence_number,
                    'arrival_time', ss.arrival_time,
                    'departure_time', ss.departure_time,
                    'is_boarding_allowed', ss.is_boarding_allowed,
                    'is_dropping_allowed', ss.is_dropping_allowed
                )
                ORDER BY rs.sequence_number
            )
            FROM schedule_stops ss
            JOIN route_stops rs
                ON rs.id = ss.route_stop_id
            WHERE ss.schedule_id = s.id
              AND ss.is_boarding_allowed = TRUE
        ),
        '[]'::jsonb
    ) AS boarding_stops,

    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'stop_id', rs.id,
                    'stop_name', rs.stop_name,
                    'city', rs.city,
                    'sequence_number', rs.sequence_number,
                    'arrival_time', ss.arrival_time,
                    'departure_time', ss.departure_time,
                    'is_boarding_allowed', ss.is_boarding_allowed,
                    'is_dropping_allowed', ss.is_dropping_allowed
                )
                ORDER BY rs.sequence_number
            )
            FROM schedule_stops ss
            JOIN route_stops rs
                ON rs.id = ss.route_stop_id
            WHERE ss.schedule_id = s.id
              AND ss.is_dropping_allowed = TRUE
        ),
        '[]'::jsonb
    ) AS dropping_stops

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

        details = dict(row._mapping)
        schedule_stops = add_day_offsets(details.pop("_schedule_stops"))
        stop_offsets = {
            str(stop["stop_id"]): stop for stop in schedule_stops
        }

        for stop_group in ("boarding_stops", "dropping_stops"):
            for stop in details[stop_group]:
                offsets = stop_offsets[str(stop["stop_id"])]
                stop.update(
                    {
                        "day_offset": offsets["day_offset"],
                        "arrival_day_offset": offsets["arrival_day_offset"],
                        "departure_day_offset": offsets["departure_day_offset"],
                        "arrival_display": format_time_display(
                            stop["arrival_time"],
                            offsets["arrival_day_offset"],
                            details.get("travel_date"),
                        ),
                        "departure_display": format_time_display(
                            stop["departure_time"],
                            offsets["departure_day_offset"],
                            details.get("travel_date"),
                        ),
                    }
                )

        return details