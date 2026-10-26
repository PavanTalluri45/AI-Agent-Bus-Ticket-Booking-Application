import json
import os
import re
import subprocess
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _render_chat_components(payload: dict) -> dict:
    frontend_root = REPO_ROOT / "frontend"
    environment = os.environ.copy()
    environment["CHAT_COMPONENT_FRONTEND_ROOT"] = str(frontend_root)
    environment["NODE_PATH"] = str(frontend_root / "node_modules")

    harness = r"""
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ts = require(path.join(process.env.CHAT_COMPONENT_FRONTEND_ROOT, "node_modules", "typescript"));
const frontend = process.env.CHAT_COMPONENT_FRONTEND_ROOT;
const sourceRoot = path.join(frontend, "components", "chat");
const outputRoot = fs.mkdtempSync(path.join(os.tmpdir(), "chat-components-test-"));
const compilerOptions = {
  module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2020,
  jsx: ts.JsxEmit.ReactJSX,
  esModuleInterop: true,
};

for (const [sourceName, outputName] of [
  ["selection-options.tsx", "selection-options.js"],
  ["seat-map.tsx", "seat-map.js"],
  ["confirmed-ticket.tsx", "confirmed-ticket.js"],
  ["seat-layout.ts", "seat-layout.js"],
]) {
  const source = fs.readFileSync(path.join(sourceRoot, sourceName), "utf8");
  const output = ts.transpileModule(source, { compilerOptions }).outputText;
  fs.writeFileSync(path.join(outputRoot, outputName), output);
}
const timeSource = fs.readFileSync(
  path.join(frontend, "lib", "format-time.ts"),
  "utf8",
);
fs.writeFileSync(
  path.join(outputRoot, "format-time.js"),
  ts.transpileModule(timeSource, { compilerOptions }).outputText,
);

const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const element = (tag) => ({ children, ...props }) =>
  React.createElement(tag, props, children);
const icon = () => React.createElement("svg", { "aria-hidden": "true" });
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "@/components/ui/card") {
    return { Card: element("section"), CardContent: element("div") };
  }
  if (request === "@/components/ui/button") {
    return { Button: element("button") };
  }
  if (request === "lucide-react") {
    return {
      Bus: icon,
      Check: icon,
      CheckCircle2: icon,
      Copy: icon,
      Printer: icon,
    };
  }
  if (request === "@/lib/format-time") {
    return require(path.join(outputRoot, "format-time.js"));
  }
  return originalLoad.call(this, request, parent, isMain);
};

const { SelectionOptions } = require(path.join(outputRoot, "selection-options.js"));
const { SeatMap } = require(path.join(outputRoot, "seat-map.js"));
const { ConfirmedTicket } = require(path.join(outputRoot, "confirmed-ticket.js"));
const optionsHtml = renderToStaticMarkup(React.createElement(SelectionOptions, {
  options: input.options,
  interactive: true,
  onSelect: () => {},
  onContinue: () => {},
}));
const disabledOptionsHtml = renderToStaticMarkup(React.createElement(SelectionOptions, {
  options: input.options,
  interactive: false,
  onSelect: () => {},
  onContinue: () => {},
}));
const stopOptionsHtml = renderToStaticMarkup(React.createElement(SelectionOptions, {
  options: input.stopOptions,
  interactive: true,
  onSelect: () => {},
  onContinue: () => {},
}));
const boardingChosenHtml = renderToStaticMarkup(React.createElement(SelectionOptions, {
  options: input.stopOptionsBoardingChosen,
  interactive: true,
  onSelect: () => {},
  onContinue: () => {},
}));
const droppingChosenHtml = renderToStaticMarkup(React.createElement(SelectionOptions, {
  options: input.stopOptionsDroppingChosen,
  interactive: true,
  onSelect: () => {},
  onContinue: () => {},
}));
const collapsedSeatMapHtml = renderToStaticMarkup(React.createElement(SeatMap, {
  data: input.seatMap,
  selectedSeat: "1A",
  interactive: true,
  onSelectSeat: () => {},
}));
const lockedSeatMapHtml = renderToStaticMarkup(React.createElement(SeatMap, {
  data: input.seatMap,
  selectedSeat: "1A",
  interactive: false,
  locked: true,
  onSelectSeat: () => {},
}));
const ticketHtml = renderToStaticMarkup(React.createElement(ConfirmedTicket, {
  ticket: input.ticket,
}));

fs.rmSync(outputRoot, { recursive: true, force: true });
process.stdout.write(JSON.stringify({
  optionsHtml,
  disabledOptionsHtml,
  stopOptionsHtml,
  boardingChosenHtml,
  droppingChosenHtml,
  collapsedSeatMapHtml,
  lockedSeatMapHtml,
  ticketHtml,
}));
"""
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps(payload),
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        env=environment,
        encoding="utf-8",
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def rendered_components():
    return _render_chat_components(
        {
            "options": {
                "kind": "bus",
                "items": [
                    {
                        "label": "YBM Travels - AC Seater (KA01AB1234)",
                        "detail": "10:15 PM → 1:00 AM (next day) · ₹350.00 · 7 seats free",
                    },
                    {
                        "label": "SRS Travels - Volvo AC (KA02CD5678)",
                        "detail": "9:30 PM → 12:30 AM (next day) · ₹450.00 · 3 seats free",
                    },
                ],
            },
            "stopOptions": {
                "kind": "stops",
                "boarding": [
                    {
                        "label": "Hyderabad",
                        "display_time": "10:15 PM",
                        "sequence_number": 1,
                    },
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                    },
                ],
                "dropping": [
                    {
                        "label": "Vijayawada",
                        "display_time": "12:00 AM",
                        "sequence_number": 1,
                    },
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                    },
                    {
                        "label": "Chennai",
                        "display_time": "6:30 AM (next day)",
                        "sequence_number": 3,
                    },
                ],
            },
            "stopOptionsBoardingChosen": {
                "kind": "stops",
                "boarding": [
                    {
                        "label": "Hyderabad",
                        "display_time": "10:15 PM",
                        "sequence_number": 1,
                    },
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                        "selected": True,
                    },
                ],
                "dropping": [
                    {
                        "label": "Vijayawada",
                        "display_time": "12:00 AM",
                        "sequence_number": 1,
                    },
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                    },
                    {
                        "label": "Chennai",
                        "display_time": "6:30 AM (next day)",
                        "sequence_number": 3,
                    },
                ],
            },
            "stopOptionsDroppingChosen": {
                "kind": "stops",
                "boarding": [
                    {
                        "label": "Hyderabad",
                        "display_time": "10:15 PM",
                        "sequence_number": 1,
                    },
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                    },
                    {
                        "label": "Chennai",
                        "display_time": "6:30 AM (next day)",
                        "sequence_number": 3,
                    },
                ],
                "dropping": [
                    {
                        "label": "Warangal",
                        "display_time": "11:30 PM",
                        "sequence_number": 2,
                        "selected": True,
                    },
                    {
                        "label": "Chennai",
                        "display_time": "6:30 AM (next day)",
                        "sequence_number": 3,
                    },
                ],
            },
            "seatMap": {
                "bus_type": "AC Seater",
                "selected_seat": "1A",
                "seats": [
                    {
                        "seat_number": "1A",
                        "seat_type": "SEATER",
                        "row_number": 1,
                        "column_number": 1,
                        "status": "available",
                    },
                    {
                        "seat_number": "1B",
                        "seat_type": "SEATER",
                        "row_number": 1,
                        "column_number": 2,
                        "status": "available",
                    },
                ],
            },
            "ticket": {
                "booking_reference": "BUS-123456",
                "status": "CONFIRMED",
                "total_amount": "350.00",
                "operator_name": "YBM Travels",
                "bus_type": "AC Seater",
                "seat_number": "1A",
                "passenger_name": "Test Passenger",
                "passenger_age": 30,
                "passenger_gender": "OTHER",
                "origin": "Hyderabad",
                "destination": "Chennai",
                "travel_date": "2026-10-26",
                "boarding_point": "Hyderabad",
                "dropping_point": "Chennai",
                "boarding_time": "22:15:00",
                "boarding_day_offset": 0,
                "dropping_time": "01:00:00",
                "dropping_day_offset": 1,
            },
        }
    )


def test_selection_options_render_accessible_buttons(rendered_components):
    html = rendered_components["optionsHtml"]
    assert html.count("<button") == 2
    assert 'aria-label="Select bus: YBM Travels - AC Seater (KA01AB1234)' in html
    assert "10:15 PM" in html
    assert "7 seats free" in html
    assert "schedule-id" not in html


def test_selection_options_disable_buttons_when_not_current(rendered_components):
    html = rendered_components["disabledOptionsHtml"]
    button_tags = re.findall(r"<button\b[^>]*>", html)
    assert len(button_tags) == 2
    assert all(re.search(r'\sdisabled(?:="")?(?=[ >])', tag) for tag in button_tags)


def test_combined_stop_picker_renders_both_columns_and_sequences(
    rendered_components,
):
    html = rendered_components["stopOptionsHtml"]
    assert "Boarding" in html
    assert "Dropping" in html
    assert "Stop 1 · 10:15 PM" in html
    assert "Stop 3 · 6:30 AM (next day)" in html
    assert 'aria-label="Continue with selected stops"' in html
    assert "Boarding stop: " not in html


def test_stop_pair_disabling_follows_sequence_order(rendered_components):
    boarding_selected_tags = re.findall(
        r"<button\b[^>]*>",
        rendered_components["boardingChosenHtml"],
    )
    dropping_candidates = [
        tag for tag in boarding_selected_tags if "Select dropping stop" in tag
    ]
    assert len(dropping_candidates) == 3
    assert re.search(r"\sdisabled(?:=\"\")?(?=[ >])", dropping_candidates[0])
    assert re.search(r"\sdisabled(?:=\"\")?(?=[ >])", dropping_candidates[1])
    assert not re.search(r"\sdisabled(?:=\"\")?(?=[ >])", dropping_candidates[2])

    dropping_selected_tags = re.findall(
        r"<button\b[^>]*>",
        rendered_components["droppingChosenHtml"],
    )
    boarding_candidates = [
        tag for tag in dropping_selected_tags if "Select boarding stop" in tag
    ]
    assert len(boarding_candidates) == 3
    assert not re.search(r"\sdisabled(?:=\"\")?(?=[ >])", boarding_candidates[0])
    assert re.search(r"\sdisabled(?:=\"\")?(?=[ >])", boarding_candidates[1])
    assert re.search(r"\sdisabled(?:=\"\")?(?=[ >])", boarding_candidates[2])


def test_selected_seat_map_renders_collapsed_and_locks_change_button(
    rendered_components,
):
    html = rendered_components["collapsedSeatMapHtml"]
    assert "Seat 1A selected" in html
    assert "<button" in html
    assert "Change seat" in html
    assert "FRONT OF BUS" not in html

    locked_html = rendered_components["lockedSeatMapHtml"]
    assert "Seat 1A selected" in locked_html
    assert "Change seat" not in locked_html


def test_confirmed_ticket_renders_boarding_and_dropping_times(rendered_components):
    html = rendered_components["ticketHtml"]
    assert "Boarding: Hyderabad \u00b7 10:15 PM" in html
    assert "Dropping: Chennai \u00b7 1:00 AM (next day)" in html
    assert "22:15:00" not in html
    assert "Direct" not in html
