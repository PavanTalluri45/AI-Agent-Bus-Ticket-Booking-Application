from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_03_mcp.tools.schedule_time_utils import (
    add_day_offsets,
    format_time_display,
)


class SearchBusesInput(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    travel_date: date


SEARCH_BUSES_SQL = """
WITH requested_stops AS (
    SELECT
        r.id AS route_id,
        origin_stop.id AS boarding_stop_id,
        origin_stop.sequence_number AS boarding_sequence,
        destination_stop.id AS dropping_stop_id,
        destination_stop.sequence_number AS dropping_sequence
    FROM routes r
    JOIN route_stops origin_stop
        ON origin_stop.route_id = r.id
       AND origin_stop.stop_name = :origin
       AND origin_stop.is_active = TRUE
       AND origin_stop.is_boarding_allowed = TRUE
    JOIN route_stops destination_stop
        ON destination_stop.route_id = r.id
       AND destination_stop.stop_name = :destination
       AND destination_stop.is_active = TRUE
       AND destination_stop.is_dropping_allowed = TRUE
    WHERE r.origin = :origin
      AND r.destination = :destination
      AND r.is_active = TRUE
      AND origin_stop.sequence_number < destination_stop.sequence_number
),
schedule_stop_times AS (
    SELECT
        ss.schedule_id,
        rs.sequence_number,
        ss.arrival_time,
        ss.departure_time
    FROM schedule_stops ss
    JOIN route_stops rs
        ON rs.id = ss.route_stop_id
)
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
    r.destination,

    origin_schedule_stop.departure_time,
    destination_schedule_stop.arrival_time,
    fare.amount AS fare,
    fare.currency,
    (
        SELECT COUNT(*)
        FROM bus_seats available_seat
        WHERE available_seat.bus_id = b.id
          AND available_seat.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM booking_seats bks
              JOIN bookings bk
                  ON bk.id = bks.booking_id
              JOIN route_stops existing_boarding
                  ON existing_boarding.id = bk.boarding_stop_id
              JOIN route_stops existing_dropping
                  ON existing_dropping.id = bk.dropping_stop_id
              WHERE bks.seat_id = available_seat.id
                AND bk.schedule_id = s.id
                AND bk.status = 'CONFIRMED'
                AND existing_boarding.sequence_number
                    < requested_stops.dropping_sequence
                AND existing_dropping.sequence_number
                    > requested_stops.boarding_sequence
          )
          AND NOT EXISTS (
              SELECT 1
              FROM seat_holds sh
              WHERE sh.schedule_id = s.id
                AND sh.seat_id = available_seat.id
                AND sh.status = 'ACTIVE'
                AND sh.expires_at > NOW()
                AND sh.boarding_sequence
                    < requested_stops.dropping_sequence
                AND sh.dropping_sequence
                    > requested_stops.boarding_sequence
          )
    ) AS free_seats,
    requested_stops.boarding_sequence AS _boarding_sequence,
    requested_stops.dropping_sequence AS _dropping_sequence,
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'sequence_number', schedule_stop_times.sequence_number,
                    'arrival_time', schedule_stop_times.arrival_time,
                    'departure_time', schedule_stop_times.departure_time
                )
                ORDER BY schedule_stop_times.sequence_number
            )
            FROM schedule_stop_times
            WHERE schedule_stop_times.schedule_id = s.id
        ),
        '[]'::jsonb
    ) AS _schedule_stops

FROM schedules s

JOIN buses b
    ON s.bus_id = b.id

JOIN operators o
    ON b.operator_id = o.id

JOIN routes r
    ON s.route_id = r.id

JOIN requested_stops
    ON requested_stops.route_id = s.route_id

JOIN schedule_stops origin_schedule_stop
    ON origin_schedule_stop.schedule_id = s.id
   AND origin_schedule_stop.route_stop_id = requested_stops.boarding_stop_id

JOIN schedule_stops destination_schedule_stop
    ON destination_schedule_stop.schedule_id = s.id
   AND destination_schedule_stop.route_stop_id = requested_stops.dropping_stop_id

JOIN fares fare
    ON fare.schedule_id = s.id
   AND fare.boarding_stop_id = requested_stops.boarding_stop_id
   AND fare.dropping_stop_id = requested_stops.dropping_stop_id
   AND fare.is_active = TRUE

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

        schedules = []
        for row in result:
            schedule = dict(row._mapping)
            stop_times = add_day_offsets(schedule.pop("_schedule_stops"))
            stop_times_by_sequence = {
                int(stop["sequence_number"]): stop for stop in stop_times
            }
            boarding_stop = stop_times_by_sequence[
                int(schedule.pop("_boarding_sequence"))
            ]
            dropping_stop = stop_times_by_sequence[
                int(schedule.pop("_dropping_sequence"))
            ]
            schedule["departure_day_offset"] = boarding_stop[
                "departure_day_offset"
            ]
            schedule["arrival_day_offset"] = dropping_stop["arrival_day_offset"]
            schedule["departure_display"] = format_time_display(
                schedule["departure_time"],
                schedule["departure_day_offset"],
            )
            schedule["arrival_display"] = format_time_display(
                schedule["arrival_time"],
                schedule["arrival_day_offset"],
            )
            schedules.append(schedule)

        return schedules