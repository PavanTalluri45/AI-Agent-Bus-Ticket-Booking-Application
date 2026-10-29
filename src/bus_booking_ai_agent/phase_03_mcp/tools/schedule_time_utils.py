from datetime import date, datetime, time, timedelta
from typing import Any


def _as_time(value: Any) -> time:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def format_date_display(value: Any, day_offset: Any = 0) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        base_date = value.date()
    elif isinstance(value, date):
        base_date = value
    else:
        value_str = str(value).strip()
        if not value_str:
            return ""
        base_date = date.fromisoformat(value_str)

    target_date = base_date + timedelta(days=int(day_offset))
    return f"{target_date.day} {target_date.strftime('%b')}"


def format_time_display(value: Any, day_offset: Any, travel_date: Any = None) -> str:
    display = _as_time(value).strftime("%I:%M %p").lstrip("0")
    offset = int(day_offset)
    if offset > 0 and travel_date is not None:
        return f"{display}, {format_date_display(travel_date, offset)}"
    return display


def add_day_offsets(stops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    offset = 0
    previous_departure: time | None = None
    offset_stops: list[dict[str, Any]] = []

    for stop in sorted(stops, key=lambda item: int(item["sequence_number"])):
        arrival = _as_time(stop["arrival_time"])
        departure = _as_time(stop["departure_time"])
        if previous_departure is not None and arrival < previous_departure:
            offset += 1

        stored_offset = stop.get("day_offset")
        arrival_offset = int(stop.get("arrival_day_offset", stored_offset if stored_offset is not None else offset))
        departure_offset = int(
            stop.get(
                "departure_day_offset",
                stored_offset if stored_offset is not None else arrival_offset + (departure < arrival),
            )
        )

        offset_stop = {
            **stop,
            "day_offset": arrival_offset,
            "arrival_day_offset": arrival_offset,
            "departure_day_offset": departure_offset,
        }
        offset_stops.append(offset_stop)
        offset = departure_offset
        previous_departure = departure

    return offset_stops
