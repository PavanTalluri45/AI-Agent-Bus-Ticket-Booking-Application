import type { SeatMapSeat } from "../../types/bus-booking";

export interface SeaterLayoutRow {
  rowNumber: number;
  left: [SeatMapSeat | null, SeatMapSeat | null];
  right: [SeatMapSeat | null, SeatMapSeat | null];
}

export interface SleeperLayoutRow {
  rowNumber: number;
  left: SeatMapSeat | null;
  right: [SeatMapSeat | null, SeatMapSeat | null];
}

export interface SleeperDeckLayout {
  seatType: "LOWER" | "UPPER";
  rows: SleeperLayoutRow[];
}

export type SeatLayout =
  | { kind: "seater"; rows: SeaterLayoutRow[] }
  | { kind: "sleeper"; decks: SleeperDeckLayout[] };

function seatNumberValue(seat: SeatMapSeat): number {
  const digits = seat.seat_number.match(/\d+/);
  return digits ? Number(digits[0]) : Number.MAX_SAFE_INTEGER;
}

function compareSeatNumbers(a: SeatMapSeat, b: SeatMapSeat): number {
  return (
    seatNumberValue(a) - seatNumberValue(b) ||
    a.seat_number.localeCompare(b.seat_number)
  );
}

function makeSleeperDeck(
  seats: SeatMapSeat[],
  seatType: "LOWER" | "UPPER",
): SleeperDeckLayout {
  const ordered = seats
    .filter((seat) => seat.seat_type === seatType)
    .sort(compareSeatNumbers);

  const rows: SleeperLayoutRow[] = [];
  for (let index = 0; index < ordered.length; index += 3) {
    rows.push({
      rowNumber: rows.length + 1,
      left: ordered[index] ?? null,
      right: [ordered[index + 1] ?? null, ordered[index + 2] ?? null],
    });
  }

  return { seatType, rows };
}

function makeSeaterRows(seats: SeatMapSeat[]): SeaterLayoutRow[] {
  const grouped = new Map<number, Array<SeatMapSeat | null>>();

  for (const seat of seats) {
    const rowNumber = seat.row_number ?? 0;
    const row = grouped.get(rowNumber) ?? [null, null, null, null];
    const requestedIndex =
      seat.column_number !== null &&
      seat.column_number >= 1 &&
      seat.column_number <= 4
        ? seat.column_number - 1
        : row.findIndex((slot) => slot === null);
    const availableIndex =
      requestedIndex >= 0 && row[requestedIndex] === null
        ? requestedIndex
        : row.findIndex((slot) => slot === null);

    if (availableIndex >= 0) {
      row[availableIndex] = seat;
    } else {
      const overflowRowNumber =
        Math.max(0, ...grouped.keys()) + 1;
      grouped.set(overflowRowNumber, [seat, null, null, null]);
      continue;
    }

    grouped.set(rowNumber, row);
  }

  return [...grouped.entries()]
    .sort(([a], [b]) => a - b)
    .map(([rowNumber, slots], index) => ({
      rowNumber: rowNumber || index + 1,
      left: [slots[0], slots[1]],
      right: [slots[2], slots[3]],
    }));
}

export function getSeatLayout(seats: SeatMapSeat[]): SeatLayout {
  const isSleeper = seats.some(
    (seat) => seat.seat_type === "LOWER" || seat.seat_type === "UPPER",
  );

  if (isSleeper) {
    return {
      kind: "sleeper",
      decks: (["LOWER", "UPPER"] as const)
        .map((seatType) => makeSleeperDeck(seats, seatType))
        .filter((deck) => deck.rows.length > 0),
    };
  }

  return { kind: "seater", rows: makeSeaterRows(seats) };
}
