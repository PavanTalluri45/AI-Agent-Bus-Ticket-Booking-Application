from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, Field
from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_03_mcp.tools.schedule_time_utils import (
    _as_time,
    add_day_offsets,
    format_time_display,
)

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def get_current_time() -> datetime:
    """Return current timestamp in Indian Standard Time (+05:30)."""
    return datetime.now(IST)


class SearchBusesInput(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    travel_date: date


SEARCH_BUSES_SQL = """
WITH requested_stops AS (
    SELECT
        r.id AS route_id,
        r.origin AS route_origin,
        r.destination AS route_destination,
        origin_stop.id AS boarding_stop_id,
        origin_stop.stop_name AS boarding_stop_name,
        origin_stop.sequence_number AS boarding_sequence,
        destination_stop.id AS dropping_stop_id,
        destination_stop.stop_name AS dropping_stop_name,
        destination_stop.sequence_number AS dropping_sequence
    FROM routes r
    JOIN route_stops origin_stop
        ON origin_stop.route_id = r.id
       AND origin_stop.stop_name ILIKE :origin
       AND origin_stop.is_active = TRUE
       AND origin_stop.is_boarding_allowed = TRUE
    JOIN route_stops destination_stop
        ON destination_stop.route_id = r.id
       AND destination_stop.stop_name ILIKE :destination
       AND destination_stop.is_active = TRUE
       AND destination_stop.is_dropping_allowed = TRUE
    WHERE r.is_active = TRUE
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
    requested_stops.route_origin,
    requested_stops.route_destination,
    requested_stops.boarding_stop_id,
    requested_stops.boarding_stop_name,
    requested_stops.dropping_stop_id,
    requested_stops.dropping_stop_name,

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
    ) AS free_seat_count,
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
    s.travel_date >= (CAST(:travel_date AS DATE) - 2)
    AND s.travel_date <= CAST(:travel_date AS DATE)
    AND s.status = 'SCHEDULED'
    AND b.is_active = TRUE
    AND o.is_active = TRUE
    AND r.is_active = TRUE

ORDER BY
    s.travel_date,
    origin_schedule_stop.departure_time,
    b.bus_number;
"""


def search_buses(
    request: SearchBusesInput,
    *,
    now: datetime | None = None,
) -> list[dict]:
    if now is None:
        now_ist = get_current_time()
    elif now.tzinfo is None:
        now_ist = now.replace(tzinfo=IST)
    else:
        now_ist = now.astimezone(IST)

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
            raw_stops = schedule.pop("_schedule_stops", [])
            stop_times = add_day_offsets(raw_stops) if raw_stops else []
            stop_times_by_sequence = {
                int(stop["sequence_number"]): stop for stop in stop_times
            }

            boarding_sequence = schedule.pop("_boarding_sequence", None)
            dropping_sequence = schedule.pop("_dropping_sequence", None)

            boarding_stop_meta = (
                stop_times_by_sequence.get(int(boarding_sequence))
                if boarding_sequence is not None
                else None
            )
            dropping_stop_meta = (
                stop_times_by_sequence.get(int(dropping_sequence))
                if dropping_sequence is not None
                else None
            )

            boarding_departure_day_offset = (
                boarding_stop_meta["departure_day_offset"]
                if boarding_stop_meta and "departure_day_offset" in boarding_stop_meta
                else int(schedule.get("departure_day_offset", 0))
            )
            dropping_arrival_day_offset = (
                dropping_stop_meta["arrival_day_offset"]
                if dropping_stop_meta and "arrival_day_offset" in dropping_stop_meta
                else int(schedule.get("arrival_day_offset", 0))
            )

            # Date rule: schedule matches if schedule.travel_date + boarding_departure_day_offset == requested_date
            schedule_travel_date = schedule.get("travel_date") or request.travel_date
            if isinstance(schedule_travel_date, datetime):
                schedule_travel_date = schedule_travel_date.date()

            boarding_date = schedule_travel_date + timedelta(
                days=boarding_departure_day_offset
            )
            if boarding_date != request.travel_date:
                continue

            # Departed buses rule: Exclude buses whose boarding departure time has passed in IST (+05:30)
            dep_time = _as_time(schedule["departure_time"])
            boarding_departure_datetime = datetime.combine(
                boarding_date, dep_time, tzinfo=IST
            )
            if boarding_departure_datetime <= now_ist:
                continue

            departure_display = format_time_display(
                schedule["departure_time"],
                boarding_departure_day_offset,
            )
            arrival_display = format_time_display(
                schedule["arrival_time"],
                dropping_arrival_day_offset,
            )

            schedule["departure_day_offset"] = boarding_departure_day_offset
            schedule["arrival_day_offset"] = dropping_arrival_day_offset
            schedule["departure_display"] = departure_display
            schedule["arrival_display"] = arrival_display

            boarding_stop_id = str(schedule.get("boarding_stop_id", ""))
            boarding_stop_name = str(schedule.get("boarding_stop_name", request.origin))
            dropping_stop_id = str(schedule.get("dropping_stop_id", ""))
            dropping_stop_name = str(schedule.get("dropping_stop_name", request.destination))

            schedule["boarding_stop_id"] = boarding_stop_id
            schedule["boarding_stop_name"] = boarding_stop_name
            schedule["dropping_stop_id"] = dropping_stop_id
            schedule["dropping_stop_name"] = dropping_stop_name

            schedule["origin"] = boarding_stop_name
            schedule["destination"] = dropping_stop_name

            schedule["boarding_stop"] = {
                "id": boarding_stop_id,
                "name": boarding_stop_name,
                "departure_display": departure_display,
            }
            schedule["dropping_stop"] = {
                "id": dropping_stop_id,
                "name": dropping_stop_name,
                "arrival_display": arrival_display,
            }

            route_origin = str(schedule.get("route_origin", ""))
            route_destination = str(schedule.get("route_destination", ""))
            is_segment = bool(
                route_origin
                and route_destination
                and (
                    boarding_stop_name.strip().casefold()
                    != route_origin.strip().casefold()
                    or dropping_stop_name.strip().casefold()
                    != route_destination.strip().casefold()
                )
            )
            schedule["is_segment_search"] = is_segment

            free_seat_count = int(
                schedule.get("free_seat_count", schedule.get("free_seats", 0))
            )
            schedule["free_seat_count"] = free_seat_count
            schedule["free_seats"] = free_seat_count  # alias for backwards compatibility

            schedules.append(schedule)

        return schedules
