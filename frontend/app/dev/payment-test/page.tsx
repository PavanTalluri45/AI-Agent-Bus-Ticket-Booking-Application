"use client";

import { useRef } from "react";

import RazorpayCheckout from "@/components/payment/RazorpayCheckout";

export default function PaymentTestPage() {
  const checkoutRef = useRef<{
    openCheckout: () => void;
  }>(null);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-bold">
          Razorpay Checkout Test
        </h1>

        <button
          type="button"
          onClick={() => checkoutRef.current?.openCheckout()}
          className="rounded-md bg-black px-6 py-3 text-white"
        >
          Test Razorpay Checkout
        </button>

        <RazorpayCheckout
          ref={checkoutRef}
          orderId="order_Tf7SCLgndv2PJU"
          amount={127000}
          currency="INR"
          bookingReference="BUS-AE840EC10E"
          paymentId="b5c78af9-5e19-4cad-9499-d4e7d6d1662c"
          userName="Pavan Talluri"
          userEmail="talluripavankumar88@gmail.com"
        />
      </div>
    </main>
  );
}