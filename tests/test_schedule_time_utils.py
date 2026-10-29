from bus_booking_ai_agent.phase_03_mcp.tools.schedule_time_utils import (
    add_day_offsets,
    format_time_display,
)


def test_add_day_offsets_marks_overnight_arrival():
    stops = add_day_offsets(
        [
            {
                "sequence_number": 1,
                "arrival_time": "22:00:00",
                "departure_time": "22:15:00",
            },
            {
                "sequence_number": 2,
                "arrival_time": "01:00:00",
                "departure_time": "01:05:00",
            },
        ]
    )

    assert stops[0]["day_offset"] == 0
    assert stops[0]["departure_day_offset"] == 0
    assert stops[1]["arrival_day_offset"] == 1
    assert stops[1]["day_offset"] == 1


def test_add_day_offsets_uses_stored_offset_when_present():
    stops = add_day_offsets(
        [
            {
                "sequence_number": 1,
                "arrival_time": "22:00:00",
                "departure_time": "22:15:00",
                "day_offset": 2,
            },
            {
                "sequence_number": 2,
                "arrival_time": "01:00:00",
                "departure_time": "01:05:00",
            },
        ]
    )

    assert stops[0]["day_offset"] == 2
    assert stops[1]["day_offset"] == 3


def test_format_time_display_uses_12_hour_time_and_positive_day_offset():
    assert format_time_display("20:30:00", 0, "2026-10-26") == "8:30 PM"
    assert format_time_display("06:30:00", 1, "2026-10-26") == "6:30 AM, 27 Oct"
