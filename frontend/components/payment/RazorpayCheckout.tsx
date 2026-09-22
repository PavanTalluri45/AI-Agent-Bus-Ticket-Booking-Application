"use client";

import Script from "next/script";
import {
  forwardRef,
  useImperativeHandle,
  useState,
} from "react";

export interface RazorpayCheckoutRef {
  openCheckout: () => void;
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: RazorpayResponse) => void;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  theme?: {
    color?: string;
  };
  modal?: {
    ondismiss?: () => void;
  };
}

interface RazorpayResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open: () => void;
}

declare global {
  interface Window {
    Razorpay: new (
      options: RazorpayOptions
    ) => RazorpayInstance;
  }
}

interface RazorpayCheckoutProps {
  orderId: string;
  amount: number;
  currency: string;
  bookingReference: string;
  paymentId: string;
  userName?: string;
  userEmail?: string;
  onSuccess?: (response: RazorpayResponse) => void;
  onDismiss?: () => void;
}

const RazorpayCheckout = forwardRef<
  RazorpayCheckoutRef,
  RazorpayCheckoutProps
>(function RazorpayCheckout(
  {
    orderId,
    amount,
    currency,
    bookingReference,
    paymentId,
    userName,
    userEmail,
    onSuccess,
    onDismiss,
  },
  ref
) {
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState<
    "idle" | "verifying" | "success" | "failed"
  >("idle");

  const verifyPayment = async (
    response: RazorpayResponse
  ) => {
    setVerificationStatus("verifying");

    try {
      const verifyResponse = await fetch(
        "/api/dev/payments/verify",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            payment_id: paymentId,
            razorpay_payment_id:
              response.razorpay_payment_id,
            razorpay_order_id:
              response.razorpay_order_id,
            razorpay_signature:
              response.razorpay_signature,
          }),
        }
      );

      const result = await verifyResponse.json();

      if (!verifyResponse.ok || !result.success) {
        console.error(
          "Payment verification failed:",
          result
        );

        setVerificationStatus("failed");
        return;
      }

      console.log(
        "Payment verified successfully:",
        result
      );

      setVerificationStatus("success");

      onSuccess?.(response);
    } catch (error) {
      console.error(
        "Payment verification request failed:",
        error
      );

      setVerificationStatus("failed");
    }
  };

  const openCheckout = () => {
    if (!scriptLoaded) {
      console.error(
        "Razorpay Checkout script is not loaded."
      );
      return;
    }

    const key =
      process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

    if (!key) {
      console.error(
        "NEXT_PUBLIC_RAZORPAY_KEY_ID is missing."
      );
      return;
    }

    setLoading(true);
    setVerificationStatus("idle");

    const options: RazorpayOptions = {
      key,
      amount,
      currency,
      name: "Bus Booking AI Agent",
      description: `Bus booking ${bookingReference}`,
      order_id: orderId,

      prefill: {
        name: userName,
        email: userEmail,
      },

      handler: async (response) => {
        setLoading(false);

        console.log(
          "Razorpay payment response:",
          response
        );

        await verifyPayment(response);
      },

      theme: {
        color: "#111827",
      },

      modal: {
        ondismiss: () => {
          setLoading(false);
          onDismiss?.();
        },
      },
    };

    const razorpay =
      new window.Razorpay(options);

    razorpay.open();
  };

  useImperativeHandle(ref, () => ({
    openCheckout,
  }));

  return (
    <>
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        strategy="lazyOnload"
        onLoad={() => {
          console.log(
            "Razorpay Checkout script loaded."
          );

          setScriptLoaded(true);
        }}
        onError={() => {
          console.error(
            "Failed to load Razorpay Checkout script."
          );

          setScriptLoaded(false);
        }}
      />

      {loading && (
        <p className="text-sm text-gray-500">
          Opening secure payment checkout...
        </p>
      )}

      {verificationStatus === "verifying" && (
        <p className="text-sm text-gray-500">
          Verifying your payment...
        </p>
      )}

      {verificationStatus === "success" && (
        <p className="text-sm text-green-600">
          Payment verified successfully.
        </p>
      )}

      {verificationStatus === "failed" && (
        <p className="text-sm text-red-600">
          Payment verification failed.
        </p>
      )}
    </>
  );
});

export default RazorpayCheckout;