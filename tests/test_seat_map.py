import csv
import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SEAT_COUNTS = {
    "AC Seater": 40,
    "Non-AC Seater": 48,
    "Volvo AC": 36,
    "AC Semi-Sleeper": 32,
    "AC Sleeper": 30,
    "Non-AC Sleeper": 32,
}


def _read_seed_data():
    data_dir = REPO_ROOT / "bus_booking_agent_data" / "data"
    with (data_dir / "buses.csv").open(encoding="utf-8", newline="") as file:
        buses = list(csv.DictReader(file))
    with (data_dir / "bus_seats.csv").open(encoding="utf-8", newline="") as file:
        seats = list(csv.DictReader(file))

    for bus in buses:
        bus["total_seats"] = int(bus["total_seats"])
    for seat in seats:
        seat["row_number"] = int(seat["row_number"]) if seat["row_number"] else None
        seat["column_number"] = (
            int(seat["column_number"]) if seat["column_number"] else None
        )
        seat["is_active"] = seat["is_active"].lower() == "true"

    return buses, seats


def _run_seat_map_harness(harness: str, payload: dict) -> dict:
    frontend_root = REPO_ROOT / "frontend"
    environment = os.environ.copy()
    environment["SEAT_MAP_FRONTEND_ROOT"] = str(frontend_root)
    environment["NODE_PATH"] = str(frontend_root / "node_modules")

    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps(payload),
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        env=environment,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def seat_layout_results():
    buses, seats = _read_seed_data()
    harness = r"""
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const ts = require(path.join(process.env.SEAT_MAP_FRONTEND_ROOT, "node_modules", "typescript"));
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const sourceRoot = path.join(process.env.SEAT_MAP_FRONTEND_ROOT, "components", "chat");
const outputRoot = fs.mkdtempSync(path.join(os.tmpdir(), "seat-map-test-"));
const compilerOptions = {
  module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2020,
  jsx: ts.JsxEmit.ReactJSX,
  esModuleInterop: true,
};

for (const name of ["seat-layout.ts", "seat-map.tsx"]) {
  const source = fs.readFileSync(path.join(sourceRoot, name), "utf8");
  const output = ts.transpileModule(source, { compilerOptions }).outputText;
  fs.writeFileSync(path.join(outputRoot, name.replace(/\.tsx?$/, ".js")), output);
}

const { getSeatLayout } = require(path.join(outputRoot, "seat-layout.js"));
const { SeatMap } = require(path.join(outputRoot, "seat-map.js"));
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const results = {};

for (const bus of input.buses) {
  const busSeats = input.seats.filter((seat) => seat.bus_id === bus.id && seat.is_active);
  const layout = getSeatLayout(busSeats.map((seat) => ({
    seat_number: seat.seat_number,
    seat_type: seat.seat_type,
    row_number: seat.row_number,
    column_number: seat.column_number,
    status: "available",
  })));

  const renderSeats = busSeats.map((seat, index) => ({
    seat_number: seat.seat_number,
    seat_type: seat.seat_type,
    row_number: seat.row_number,
    column_number: seat.column_number,
    status: ["available", "unavailable", "held_by_you"][index % 3],
  }));
  const html = renderToStaticMarkup(React.createElement(SeatMap, {
    data: {
      bus_type: bus.bus_type,
      selected_seat: renderSeats.find((seat) => seat.status === "available")?.seat_number ?? null,
      seats: renderSeats,
    },
    interactive: true,
    onSelectSeat: () => {},
  }));
  const buttons = html.match(/<button\b[^>]*>/g) ?? [];
  results[bus.id] = {
    layout,
    activeSeatNumbers: busSeats.map((seat) => seat.seat_number),
    buttonCount: buttons.length,
    disabledCount: buttons.filter((button) => /\sdisabled(?:=|\s|>)/.test(button)).length,
    renderedLabels: buttons.filter((button) => /aria-label="Seat /.test(button)).length,
  };
}

fs.rmSync(outputRoot, { recursive: true, force: true });
process.stdout.write(JSON.stringify(results));
"""
    return _run_seat_map_harness(harness, {"buses": buses, "seats": seats})


def _layout_seats(layout: dict) -> list[dict]:
    if layout["kind"] == "seater":
        return [
            seat
            for row in layout["rows"]
            for seat in [*row["left"], *row["right"]]
            if seat is not None
        ]
    return [
        seat
        for deck in layout["decks"]
        for row in deck["rows"]
        for seat in [row["left"], *row["right"]]
        if seat is not None
    ]


def _numeric_seat_order(seat: dict) -> int:
    digits = "".join(character for character in seat["seat_number"] if character.isdigit())
    return int(digits) if digits else 2**53 - 1


def test_layout_places_every_seed_seat_and_follows_design(seat_layout_results):
    buses, seats = _read_seed_data()
    observed_types = set()

    for bus in buses:
        observed_types.add(bus["bus_type"])
        active_seats = [
            seat
            for seat in seats
            if seat["bus_id"] == bus["id"] and seat["is_active"]
        ]
        result = seat_layout_results[bus["id"]]
        layout = result["layout"]
        placed = _layout_seats(layout)
        assert len(placed) == bus["total_seats"]
        assert len(placed) == len(active_seats)
        assert sorted(seat["seat_number"] for seat in placed) == sorted(
            seat["seat_number"] for seat in active_seats
        )
        assert len({seat["seat_number"] for seat in placed}) == len(placed)

        if layout["kind"] == "sleeper":
            assert {deck["seatType"] for deck in layout["decks"]} == {
                "LOWER",
                "UPPER",
            }
            for deck in layout["decks"]:
                expected = sorted(
                    (
                        seat
                        for seat in active_seats
                        if seat["seat_type"] == deck["seatType"]
                    ),
                    key=lambda seat: (
                        _numeric_seat_order(seat),
                        seat["seat_number"],
                    ),
                )
                actual = [
                    seat
                    for row in deck["rows"]
                    for seat in [row["left"], *row["right"]]
                    if seat is not None
                ]
                assert [seat["seat_number"] for seat in actual] == [
                    seat["seat_number"] for seat in expected
                ]
                for index, row in enumerate(deck["rows"]):
                    expected_group = expected[index * 3 : index * 3 + 3]
                    actual_group = [
                        seat
                        for seat in [row["left"], *row["right"]]
                        if seat is not None
                    ]
                    assert [seat["seat_number"] for seat in actual_group] == [
                        seat["seat_number"] for seat in expected_group
                    ]
        else:
            for row in layout["rows"]:
                source_row = [
                    seat
                    for seat in active_seats
                    if seat["row_number"] == row["rowNumber"]
                ]
                for seat in source_row:
                    column_index = seat["column_number"] - 1
                    actual = (
                        row["left"][column_index]
                        if column_index < 2
                        else row["right"][column_index - 2]
                    )
                    assert actual["seat_number"] == seat["seat_number"]

    assert observed_types == set(EXPECTED_SEAT_COUNTS)
    assert {
        bus_type: EXPECTED_SEAT_COUNTS[bus_type] for bus_type in observed_types
    } == EXPECTED_SEAT_COUNTS
    for bus in buses:
        assert bus["total_seats"] == EXPECTED_SEAT_COUNTS[bus["bus_type"]]


def test_seat_map_renders_expected_buttons_for_all_bus_types(seat_layout_results):
    buses, _ = _read_seed_data()

    for bus in buses:
        result = seat_layout_results[bus["id"]]
        expected = bus["total_seats"]
        available_count = sum(
            index % 3 == 0 for index in range(expected)
        )
        assert result["buttonCount"] == expected
        assert result["renderedLabels"] == expected
        assert result["disabledCount"] == expected - available_count
