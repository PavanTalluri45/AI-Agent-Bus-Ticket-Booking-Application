"use client";

import { useState } from "react";
import type { SeatMapData, SeatMapSeat } from "@/types/bus-booking";
import { getSeatLayout } from "./seat-layout";

/**
 * Seat map that follows Bus Seat Map.html exactly:
 *  - Seater / semi-sleeper: 44x50 seats, 88px per side of the aisle, a 36px
 *    row-number column in the middle, "FRONT OF BUS" above.
 *  - Sleeper: two decks side by side (40px apart). Every row has ONE berth on
 *    the left (44px column) and TWO berths side by side on the right, with a
 *    28px gap between them. 44x88 berths, pillow end at the bottom.
 * Only colours change with seat state; the geometry never does.
 */

interface SeatMapProps {
  data: SeatMapData;
  interactive: boolean;
  onSelectSeat: (seatNumber: string) => void;
  locked?: boolean;
  /** Seat the application resolved. Falls back to the one stored in the map. */
  selectedSeat?: string | null;
}

type VisualState = "available" | "selected" | "held" | "unavailable";

const STATUS_LABELS: Record<VisualState, string> = {
  available: "available",
  selected: "selected",
  held: "held for you",
  unavailable: "unavailable",
};

const TEXT_CLASSES: Record<VisualState, string> = {
  available: "text-foreground",
  selected: "text-primary",
  held: "text-emerald-600 dark:text-emerald-400",
  unavailable: "text-muted-foreground/50",
};

const FILL_CLASSES: Record<VisualState, string> = {
  available: "",
  selected: "fill-current",
  held: "fill-current",
  unavailable: "fill-muted",
};

function visualState(seat: SeatMapSeat, selectedSeat: string | null): VisualState {
  if (seat.status === "unavailable") return "unavailable";
  if (seat.status === "held_by_you") return "held";
  if (seat.seat_number === selectedSeat) return "selected";
  return "available";
}

function SeaterIcon({ fillClass }: { fillClass: string }) {
  return (
    <svg
      width="26"
      height="27"
      viewBox="0 0 26 27"
      fill="none"
      aria-hidden="true"
      className={fillClass}
    >
      <path
        d="M2.84395 9.51877V4.40002C2.84395 2.61252 4.30644 1.15002 6.09394 1.15002H19.9064C21.6939 1.15002 23.1564 2.61252 23.1564 4.40002V9.51877M22.9939 9.51877H22.2627C21.6127 9.51877 21.1252 10.0875 21.1252 10.6563V17.725C21.1252 19.675 19.5814 21.2188 17.6314 21.2188H8.45019C6.50019 21.2188 4.95644 19.675 4.95644 17.725V10.6563C4.95644 10.0063 4.46894 9.51877 3.81894 9.51877H3.00645C1.70645 9.51877 0.731445 10.575 0.731445 11.7938V22.5188C0.731445 24.3063 2.19395 25.7688 3.98145 25.7688H22.1002C23.8877 25.7688 25.3502 24.3063 25.3502 22.5188V11.875C25.3502 10.575 24.2939 9.51877 22.9939 9.51877Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeMiterlimit="10"
      />
    </svg>
  );
}

function BerthIcon({
  fillClass,
  filled,
}: {
  fillClass: string;
  filled: boolean;
}) {
  return (
    <svg
      width="32"
      height="70"
      viewBox="0 0 32 70"
      fill="none"
      aria-hidden="true"
      className={fillClass}
    >
      <rect
        x="0.75"
        y="0.75"
        width="30.5"
        height="68.5"
        rx="5.25"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <rect
        x="6"
        y="58.5"
        width="20"
        height="6"
        rx="2"
        fill={filled ? "#ffffff" : "currentColor"}
        fillOpacity={filled ? 0.55 : 0.2}
      />
    </svg>
  );
}

function SeatButton({
  seat,
  sleeper,
  selectedSeat,
  interactive,
  onSelectSeat,
}: {
  seat: SeatMapSeat;
  sleeper: boolean;
  selectedSeat: string | null;
  interactive: boolean;
  onSelectSeat: (seatNumber: string) => void;
}) {
  const state = visualState(seat, selectedSeat);
  const filled = state === "selected" || state === "held";
  const canClick = interactive && seat.status === "available";

  return (
    <button
      type="button"
      aria-label={`Seat ${seat.seat_number}, ${STATUS_LABELS[state]}`}
      aria-pressed={state === "selected"}
      disabled={!canClick}
      onClick={() => {
        if (state !== "selected") onSelectSeat(seat.seat_number);
      }}
      className={`flex w-11 flex-col items-center justify-center gap-0.5 rounded-lg ${
        sleeper ? "h-[88px]" : "h-[50px]"
      } ${TEXT_CLASSES[state]} ${
        state === "available" && canClick ? "hover:bg-muted" : ""
      } disabled:cursor-default`}
    >
      {sleeper ? (
        <BerthIcon fillClass={FILL_CLASSES[state]} filled={filled} />
      ) : (
        <SeaterIcon fillClass={FILL_CLASSES[state]} />
      )}
      <span className="text-[11px] font-semibold leading-none">
        {seat.seat_number}
      </span>
    </button>
  );
}

function Legend() {
  const items: { state: VisualState; label: string }[] = [
    { state: "available", label: "Available" },
    { state: "selected", label: "Selected" },
    { state: "held", label: "Held for you" },
    { state: "unavailable", label: "Unavailable" },
  ];
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map(({ state, label }) => (
        <span
          key={state}
          className={`flex items-center gap-1.5 ${TEXT_CLASSES[state]}`}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <rect
              className={FILL_CLASSES[state]}
              x="1"
              y="1"
              width="12"
              height="12"
              rx="3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
          <span className="text-muted-foreground">{label}</span>
        </span>
      ))}
    </div>
  );
}

export function SeatMap({
  data,
  interactive,
  onSelectSeat,
  locked = false,
  selectedSeat,
}: SeatMapProps) {
  const layout = getSeatLayout(data.seats);
  const selected = selectedSeat !== undefined ? selectedSeat : data.selected_seat;
  const [expanded, setExpanded] = useState(false);
  const available = data.seats.filter((s) => s.status === "available").length;
  const buttonProps = {
    selectedSeat: selected,
    interactive: interactive && !locked,
    onSelectSeat,
  };

  if (selected && !expanded) {
    return (
      <section
        aria-label="Seat selection"
        className="mt-3 flex w-full max-w-[480px] items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3 text-card-foreground"
      >
        <span className="text-sm font-medium">Seat {selected} selected</span>
        {!locked && (
          <button
            type="button"
            aria-label={`Change selected seat ${selected}`}
            disabled={!interactive}
            onClick={() => setExpanded(true)}
            className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-60"
          >
            Change seat
          </button>
        )}
      </section>
    );
  }

  let subtitle: string;
  if (layout.kind === "sleeper") {
    const lower = data.seats.filter((s) => s.seat_type === "LOWER").length;
    const upper = data.seats.filter((s) => s.seat_type === "UPPER").length;
    subtitle = `${data.seats.length} berths · ${lower} lower, ${upper} upper · 1 + 2 per deck`;
  } else {
    subtitle = `${data.seats.length} seats · ${layout.rows.length} rows · 2 + 2 seater`;
  }

  return (
    <section
      aria-label={`Seat map${data.bus_type ? ` for ${data.bus_type}` : ""}`}
      className="mt-3 flex w-full max-w-[480px] flex-col gap-4 rounded-2xl border border-border bg-card p-6 text-card-foreground"
    >
      <div>
        <h3 className="m-0 text-xl font-semibold">{data.bus_type ?? "Seat map"}</h3>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {subtitle} · {available} available
        </p>
      </div>

      <div className="overflow-x-auto">
        {layout.kind === "seater" ? (
          <div className="flex flex-col items-center gap-0.5">
            <div className="mb-1.5 text-[11px] tracking-[0.08em] text-muted-foreground">
              FRONT OF BUS
            </div>
            {layout.rows.map((row) => (
              <div key={row.rowNumber} className="flex items-center">
                <div className="flex w-[88px]">
                  {row.left.map((seat, index) =>
                    seat ? (
                      <SeatButton
                        key={seat.seat_number}
                        seat={seat}
                        sleeper={false}
                        {...buttonProps}
                      />
                    ) : (
                      <span key={`l-${index}`} className="w-11" aria-hidden="true" />
                    ),
                  )}
                </div>
                <div className="w-9 text-center text-[11px] text-muted-foreground">
                  {row.rowNumber}
                </div>
                <div className="flex w-[88px]">
                  {row.right.map((seat, index) =>
                    seat ? (
                      <SeatButton
                        key={seat.seat_number}
                        seat={seat}
                        sleeper={false}
                        {...buttonProps}
                      />
                    ) : (
                      <span key={`r-${index}`} className="w-11" aria-hidden="true" />
                    ),
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-wrap justify-center gap-x-10 gap-y-6">
            {layout.decks.map((deck) => (
              <div key={deck.seatType} className="flex flex-col gap-0.5">
                <div className="mb-1.5 text-xs font-semibold tracking-[0.06em] text-muted-foreground">
                  {deck.seatType} DECK
                </div>
                {deck.rows.map((row) => (
                  <div key={row.rowNumber} className="flex gap-7">
                    <div className="w-11">
                      {row.left && (
                        <SeatButton seat={row.left} sleeper {...buttonProps} />
                      )}
                    </div>
                    <div className="flex gap-1">
                      {row.right.map(
                        (seat) =>
                          seat && (
                            <SeatButton
                              key={seat.seat_number}
                              seat={seat}
                              sleeper
                              {...buttonProps}
                            />
                          ),
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      <Legend />
    </section>
  );
}
