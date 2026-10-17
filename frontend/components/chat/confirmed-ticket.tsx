"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  Copy,
  Check,
  Bus,
  Calendar,
  MapPin,
  User,
  Ticket,
  Printer,
} from "lucide-react";
import type { ConfirmedTicketData } from "@/types/bus-booking";

interface ConfirmedTicketProps {
  ticket: ConfirmedTicketData;
  onBookAnother?: () => void;
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
    <Card className="border-emerald-300 dark:border-emerald-800 bg-gradient-to-b from-emerald-50/70 via-background to-background dark:from-emerald-950/20 dark:via-background dark:to-background shadow-md overflow-hidden mt-4 mb-2 print:border-none print:shadow-none">
      {/* Header Banner */}
      <CardHeader className="bg-emerald-600 text-white px-5 py-3.5 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className="w-5 h-5 text-white" />
          <div>
            <CardTitle className="text-base font-bold text-white tracking-wide">
              Booking Confirmed
            </CardTitle>
            <p className="text-xs text-emerald-100">
              Your ticket has been confirmed and seat reserved.
            </p>
          </div>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-800 text-emerald-100">
          {ticket.status}
        </span>
      </CardHeader>

      <CardContent className="p-5 space-y-5">
        {/* Reference & Actions Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-muted/40 rounded-lg border">
          <div>
            <div className="text-xs text-muted-foreground uppercase font-medium tracking-wider">
              Booking Reference
            </div>
            <div className="font-mono text-base font-bold text-foreground">
              {ticket.booking_reference}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="xs"
              onClick={handleCopy}
              className="text-xs h-8 gap-1.5"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  Copy Ref
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="xs"
              onClick={handlePrint}
              className="text-xs h-8 gap-1.5 print:hidden"
            >
              <Printer className="w-3.5 h-3.5" />
              Print
            </Button>
          </div>
        </div>

        {/* Route Header */}
        {(ticket.origin || ticket.destination) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-center py-2 border-b">
            <div>
              <div className="text-xs text-muted-foreground">From</div>
              <div className="font-semibold text-base">{ticket.origin || "—"}</div>
              {ticket.boarding_point && (
                <div className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                  <MapPin className="w-3 h-3 text-muted-foreground" />
                  Boarding: {ticket.boarding_point}
                </div>
              )}
            </div>
            <div className="text-center hidden sm:block">
              <Bus className="w-5 h-5 mx-auto text-emerald-600 dark:text-emerald-400" />
              <div className="text-[11px] text-muted-foreground mt-0.5">Direct Service</div>
            </div>
            <div className="sm:text-right">
              <div className="text-xs text-muted-foreground">To</div>
              <div className="font-semibold text-base">{ticket.destination || "—"}</div>
              {ticket.dropping_point && (
                <div className="text-xs text-muted-foreground flex items-center gap-1 sm:justify-end mt-0.5">
                  <MapPin className="w-3 h-3 text-muted-foreground" />
                  Dropping: {ticket.dropping_point}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Details Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          {ticket.travel_date && (
            <div>
              <span className="text-muted-foreground flex items-center gap-1 mb-1">
                <Calendar className="w-3.5 h-3.5 text-muted-foreground" /> Travel Date
              </span>
              <p className="font-semibold text-sm">{ticket.travel_date}</p>
            </div>
          )}

          {ticket.seat_number && (
            <div>
              <span className="text-muted-foreground flex items-center gap-1 mb-1">
                <Ticket className="w-3.5 h-3.5 text-muted-foreground" /> Seat No.
              </span>
              <p className="font-semibold text-sm text-emerald-600 dark:text-emerald-400">
                {ticket.seat_number}
              </p>
            </div>
          )}

          {ticket.operator_name && (
            <div>
              <span className="text-muted-foreground flex items-center gap-1 mb-1">
                <Bus className="w-3.5 h-3.5 text-muted-foreground" /> Operator
              </span>
              <p className="font-semibold text-sm">{ticket.operator_name}</p>
              {ticket.bus_type && (
                <p className="text-[11px] text-muted-foreground">{ticket.bus_type}</p>
              )}
            </div>
          )}

          {ticket.total_amount && (
            <div>
              <span className="text-muted-foreground mb-1 block">Total Amount Paid</span>
              <p className="font-bold text-base text-foreground">
                ₹{ticket.total_amount}
              </p>
            </div>
          )}
        </div>

        {/* Passenger Info */}
        {(ticket.passenger_name || ticket.passenger_age || ticket.passenger_gender) && (
          <div className="p-3 rounded-lg bg-muted/30 border text-xs">
            <span className="text-muted-foreground font-medium flex items-center gap-1.5 mb-1.5">
              <User className="w-3.5 h-3.5 text-muted-foreground" /> Passenger Information
            </span>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              {ticket.passenger_name && (
                <span className="font-semibold text-foreground">
                  {ticket.passenger_name}
                </span>
              )}
              {ticket.passenger_age && (
                <span className="text-muted-foreground">Age: {ticket.passenger_age}</span>
              )}
              {ticket.passenger_gender && (
                <span className="text-muted-foreground">
                  Gender: {ticket.passenger_gender}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Footer Actions */}
        {onBookAnother && (
          <div className="pt-2 flex justify-end print:hidden">
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

