"use client";

import { useState } from "react";
import type {
  SelectionOptionsData,
  StopSelectionOptionItem,
} from "@/types/bus-booking";

interface SelectionOptionsProps {
  options: SelectionOptionsData;
  interactive: boolean;
  onSelect: (label: string) => void;
  onContinue: (
    boarding: StopSelectionOptionItem,
    dropping: StopSelectionOptionItem,
  ) => void;
}

export function isStopPairValid(
  boardingSequence: number,
  droppingSequence: number,
) {
  return droppingSequence > boardingSequence;
}

export function SelectionOptions({
  options,
  interactive,
  onSelect,
  onContinue,
}: SelectionOptionsProps) {
  const [selectedBusIndex, setSelectedBusIndex] = useState<number | null>(null);
  const [selectedBoardingSequence, setSelectedBoardingSequence] = useState<
    number | null
  >(
    options.kind === "stops"
      ? options.boarding.find((item) => item.selected)?.sequence_number ?? null
      : null,
  );
  const [selectedDroppingSequence, setSelectedDroppingSequence] = useState<
    number | null
  >(
    options.kind === "stops"
      ? options.dropping.find((item) => item.selected)?.sequence_number ?? null
      : null,
  );
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  if (options.kind === "bus") {
    return (
      <div className="mt-2 flex w-full max-w-md flex-col gap-2">
        {options.items.map((item, index) => (
          <button
            key={`${item.label}-${index}`}
            type="button"
            aria-label={`Select bus: ${item.label}, ${item.detail}`}
            aria-pressed={selectedBusIndex === index}
            disabled={!interactive || selectedBusIndex !== null}
            onClick={() => {
              setSelectedBusIndex(index);
              onSelect(item.label);
            }}
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-left text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-60"
          >
            <span className="block text-sm font-medium">{item.label}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {item.detail}
            </span>
          </button>
        ))}
      </div>
    );
  }

  const selectedBoarding =
    options.boarding.find(
      (stop) => stop.sequence_number === selectedBoardingSequence,
    ) ?? null;
  const selectedDropping =
    options.dropping.find(
      (stop) => stop.sequence_number === selectedDroppingSequence,
    ) ?? null;

  const renderStopColumn = (
    label: string,
    stops: StopSelectionOptionItem[],
    selectedSequence: number | null,
    otherSequence: number | null,
    onSelectStop: (sequence: number) => void,
    isBoarding: boolean,
  ) => (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <h3 className="text-sm font-semibold text-foreground">{label === "Boarding" ? "Boarding Points" : "Dropping Points"}</h3>
      <div className="flex flex-col gap-2">
        {stops.map((stop, index) => {
          const pairIsInvalid =
            otherSequence !== null &&
            (isBoarding
              ? !isStopPairValid(stop.sequence_number, otherSequence)
              : !isStopPairValid(otherSequence, stop.sequence_number));
          const selected = selectedSequence === stop.sequence_number;

          return (
            <button
              key={`${stop.sequence_number}-${stop.label}-${index}`}
              type="button"
              aria-label={`Select ${isBoarding ? "boarding" : "dropping"} stop ${stop.label}${stop.city ? ` in ${stop.city}` : ""}, ${stop.display_time}`}
              aria-pressed={selected}
              aria-disabled={pairIsInvalid}
              disabled={!interactive}
              onClick={() => {
                if (!interactive) return;
                if (pairIsInvalid) {
                  if (isBoarding) {
                    const targetDropping = options.dropping.find(
                      (item) => item.sequence_number === otherSequence,
                    );
                    setFeedbackMessage(
                      `Choose a boarding stop before ${targetDropping?.label || "dropping stop"}`,
                    );
                  } else {
                    const targetBoarding = options.boarding.find(
                      (item) => item.sequence_number === otherSequence,
                    );
                    setFeedbackMessage(
                      `Choose a dropping stop after ${targetBoarding?.label || "boarding stop"}`,
                    );
                  }
                  return;
                }
                setFeedbackMessage(null);
                onSelectStop(stop.sequence_number);
              }}
              className={`w-full rounded-xl border px-3 py-2 text-left text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-60 ${
                pairIsInvalid
                  ? "cursor-not-allowed opacity-50 border-border bg-background"
                  : selected
                    ? "border-primary bg-primary/5 hover:bg-primary/10"
                    : "border-border bg-background hover:bg-muted"
              }`}
            >
              <span className="block text-sm font-medium">{stop.label}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                {stop.city ? `${stop.city} • ` : ""}
                {stop.display_time}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="mt-2 flex w-full max-w-md flex-col gap-3">
      {feedbackMessage && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center justify-between rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          <span>{feedbackMessage}</span>
          <button
            type="button"
            aria-label="Dismiss feedback message"
            onClick={() => setFeedbackMessage(null)}
            className="ml-2 rounded p-0.5 hover:bg-destructive/20"
          >
            ✕
          </button>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        {renderStopColumn(
          "Boarding",
          options.boarding,
          selectedBoardingSequence,
          selectedDroppingSequence,
          setSelectedBoardingSequence,
          true,
        )}
        {renderStopColumn(
          "Dropping",
          options.dropping,
          selectedDroppingSequence,
          selectedBoardingSequence,
          setSelectedDroppingSequence,
          false,
        )}
      </div>
      <button
        type="button"
        aria-label="Continue with selected stops"
        disabled={
          !interactive ||
          !selectedBoarding ||
          !selectedDropping ||
          !isStopPairValid(
            selectedBoarding.sequence_number,
            selectedDropping.sequence_number,
          )
        }
        onClick={() => {
          if (selectedBoarding && selectedDropping) {
            onContinue(selectedBoarding, selectedDropping);
          }
        }}
        className="w-full rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-60"
      >
        Continue
      </button>
    </div>
  );
}
