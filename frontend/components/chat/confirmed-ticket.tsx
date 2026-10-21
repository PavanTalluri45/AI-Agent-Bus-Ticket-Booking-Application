"use client";

import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bus, Check, CheckCircle2, Copy, Printer } from "lucide-react";
import type { ConfirmedTicketData } from "@/types/bus-booking";

interface ConfirmedTicketProps {
  ticket: ConfirmedTicketData;
  onBookAnother?: () => void;
}

function Field({
  label,
  children,
  sub,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  sub?: string | null;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 truncate text-sm font-semibold text-foreground">
        {children}
      </div>
      {sub && (
        <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
          {sub}
        </div>
      )}
    </div>
  );
}

export function ConfirmedTicket({ ticket, onBookAnother }: ConfirmedTicketProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (ticket.booking_reference) {
      navigator.clipboard.writeText(ticket.booking_reference);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  return (
    <Card className="mt-4 mb-2 gap-0 overflow-hidden border-emerald-300 bg-gradient-to-b from-emerald-50/70 via-background to-background py-0 shadow-md dark:border-emerald-800 dark:from-emerald-950/20 dark:via-background dark:to-background print:border-none print:shadow-none">
      {/* Header banner */}
      <div className="flex items-center justify-between gap-3 bg-emerald-600 px-5 py-3.5 text-white">
        <div className="flex min-w-0 items-center gap-3">
          <CheckCircle2 className="size-6 shrink-0" />
          <div className="min-w-0">
            <div className="text-base font-bold leading-tight tracking-wide">
              Booking Confirmed
            </div>
            <p className="truncate text-xs text-emerald-100">
              Your ticket has been confirmed and seat reserved.
            </p>
          </div>
        </div>
        <span className="shrink-0 rounded-full bg-emerald-800 px-2.5 py-0.5 text-xs font-semibold uppercase text-emerald-100">
          {ticket.status}
        </span>
      </div>

      <CardContent className="space-y-5 p-5">
        {/* Reference + actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/40 px-4 py-3">
          <div className="min-w-0">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Booking Reference
            </div>
            <div className="mt-0.5 font-mono text-base font-bold text-foreground">
              {ticket.booking_reference}
            </div>
          </div>
          <div className="flex items-center gap-2 print:hidden">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="h-8 gap-1.5 text-xs"
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy Ref"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePrint}
              className="h-8 gap-1.5 text-xs"
            >
              <Printer className="size-3.5" />
              Print
            </Button>
          </div>
        </div>

        {/* Route: From — line — To */}
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-4">
          <div className="min-w-0">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              From
            </div>
            <div className="mt-1 truncate text-lg font-bold leading-tight">
              {ticket.origin || "—"}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {ticket.boarding_point ? `Boarding: ${ticket.boarding_point}` : "\u00A0"}
            </div>
          </div>

          <div className="flex w-16 flex-col items-center gap-1 sm:w-28">
            <div className="flex w-full items-center">
              <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
              <span className="h-px flex-1 border-t border-dashed border-muted-foreground/50" />
              <Bus className="mx-1 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span className="h-px flex-1 border-t border-dashed border-muted-foreground/50" />
              <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
            </div>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Direct
            </span>
          </div>

          <div className="min-w-0 text-right">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              To
            </div>
            <div className="mt-1 truncate text-lg font-bold leading-tight">
              {ticket.destination || "—"}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {ticket.dropping_point ? `Dropping: ${ticket.dropping_point}` : "\u00A0"}
            </div>
          </div>
        </div>

        {/* Trip + passenger share one 4-column grid so columns line up */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-5 border-t border-dashed pt-5 sm:grid-cols-4">
          <Field label="Travel Date">{ticket.travel_date || "—"}</Field>
          <Field label="Seat No.">
            <span className="text-emerald-600 dark:text-emerald-400">
              {ticket.seat_number || "—"}
            </span>
          </Field>
          <Field label="Operator" sub={ticket.bus_type}>
            {ticket.operator_name || "—"}
          </Field>
          <Field label="Amount Paid">
            <span className="text-base font-bold">
              {ticket.total_amount ? `₹${ticket.total_amount}` : "—"}
            </span>
          </Field>

          <Field label="Passenger" className="col-span-2">
            {ticket.passenger_name || "—"}
          </Field>
          <Field label="Age">{ticket.passenger_age || "—"}</Field>
          <Field label="Gender">{ticket.passenger_gender || "—"}</Field>
        </div>

        {onBookAnother && (
          <div className="flex justify-end border-t pt-4 print:hidden">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onBookAnother}
              className="text-xs"
            >
              Book Another Ticket
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}