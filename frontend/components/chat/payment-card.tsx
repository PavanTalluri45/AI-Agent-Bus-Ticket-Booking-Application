"use client";

import React from "react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CreditCard, Loader2, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import type { BookingSummary, PaymentOrderSummary } from "@/types/bus-booking";

interface PaymentCardProps {
  paymentOrder: PaymentOrderSummary;
  booking?: BookingSummary;
  isPaymentOpen: boolean;
  isVerifying: boolean;
  onOpenCheckout: () => void;
  disabled?: boolean;
}

export function PaymentCard({
  paymentOrder,
  booking,
  isPaymentOpen,
  isVerifying,
  onOpenCheckout,
  disabled = false,
}: PaymentCardProps) {
  const formattedAmount = (paymentOrder.amount / 100).toFixed(2);

  return (
    <Card className="border-indigo-300 dark:border-indigo-800 bg-indigo-50/60 dark:bg-indigo-950/20 shadow-sm mt-3 mb-2">
      <CardHeader className="pb-2 pt-4 px-4 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
          <CreditCard className="w-5 h-5 flex-shrink-0" />
          <CardTitle className="text-sm font-semibold tracking-wide uppercase">
            Payment Order Initiated
          </CardTitle>
        </div>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
          PAYMENT PENDING
        </span>
      </CardHeader>

      <CardContent className="px-4 py-3 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 rounded-lg bg-background/80 border border-indigo-100 dark:border-indigo-900/50 gap-2">
          <div>
            <div className="text-xs text-muted-foreground">Order Reference</div>
            <div className="font-mono text-sm font-semibold">
              {paymentOrder.order_id}
            </div>
            {booking?.booking_reference && (
              <div className="text-xs text-muted-foreground mt-0.5">
                Booking Ref: <span className="font-mono">{booking.booking_reference}</span>
              </div>
            )}
          </div>
          <div className="sm:text-right">
            <div className="text-xs text-muted-foreground">Total Fare Payable</div>
            <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400">
              ₹{formattedAmount}
            </div>
          </div>
        </div>

        {isVerifying ? (
          <div className="flex items-center gap-2.5 p-2.5 bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-md text-xs text-blue-700 dark:text-blue-300">
            <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
            <span>Verifying Razorpay payment signature & finalizing booking...</span>
          </div>
        ) : isPaymentOpen ? (
          <div className="flex items-center gap-2 p-2.5 bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-md text-xs text-amber-700 dark:text-amber-300">
            <Sparkles className="w-4 h-4 flex-shrink-0 animate-pulse" />
            <span>Razorpay Checkout modal is currently open. Please complete the test payment.</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldAlert className="w-4 h-4 flex-shrink-0 text-muted-foreground" />
            <span>Secure 256-bit encrypted checkout via Razorpay test gateway.</span>
          </div>
        )}
      </CardContent>

      <CardFooter className="px-4 pb-4 pt-1 flex justify-end">
        {!isVerifying && (
          <Button
            type="button"
            size="sm"
            onClick={onOpenCheckout}
            disabled={disabled || isPaymentOpen || isVerifying}
            className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
          >
            {isPaymentOpen ? (
              <>
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                Checkout Open...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-1.5" />
                Open Razorpay Checkout
              </>
            )}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

