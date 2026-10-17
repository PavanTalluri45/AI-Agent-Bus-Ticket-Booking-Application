/**
 * Razorpay script loader and checkout helper.
 * Strictly runs in the browser and uses only NEXT_PUBLIC_RAZORPAY_KEY_ID.
 */

import type {
  RazorpayOptions,
  RazorpayResponsePayload,
} from "@/types/bus-booking";

export type RazorpayPaymentSuccessResponse = RazorpayResponsePayload;

export interface RazorpayCheckoutOptions {
  orderId: string;
  amount: number; // in paise
  currency?: string;
  bookingReference: string;
  userName?: string;
  userEmail?: string;
}

let razorpayScriptLoadingPromise: Promise<boolean> | null = null;

/**
 * Loads the Razorpay checkout.js script once in the browser.
 */
export function loadRazorpayScript(): Promise<boolean> {
  if (typeof window === "undefined") {
    return Promise.resolve(false);
  }

  if (window.Razorpay) {
    return Promise.resolve(true);
  }

  if (razorpayScriptLoadingPromise) {
    return razorpayScriptLoadingPromise;
  }

  razorpayScriptLoadingPromise = new Promise((resolve) => {
    // Check if script tag already exists
    const existingScript = document.querySelector(
      'script[src="https://checkout.razorpay.com/v1/checkout.js"]'
    );
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(true));
      existingScript.addEventListener("error", () => resolve(false));
      return;
    }

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;

    script.onload = () => {
      resolve(true);
    };

    script.onerror = () => {
      console.error("Failed to load Razorpay Checkout script.");
      razorpayScriptLoadingPromise = null;
      resolve(false);
    };

    document.body.appendChild(script);
  });

  return razorpayScriptLoadingPromise;
}

/**
 * Opens the Razorpay Checkout modal for an order.
 * Resolves with the Razorpay payment response when payment succeeds.
 * Rejects when dismissed or if key/script is missing.
 */
export async function openRazorpayCheckout(
  options: RazorpayCheckoutOptions
): Promise<RazorpayPaymentSuccessResponse> {
  const loaded = await loadRazorpayScript();
  if (!loaded || !window.Razorpay) {
    throw new Error("Razorpay Checkout SDK is not available.");
  }

  const key = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
  if (!key) {
    throw new Error(
      "NEXT_PUBLIC_RAZORPAY_KEY_ID is missing in frontend environment."
    );
  }

  return new Promise((resolve, reject) => {
    let resolved = false;

    const rzpOptions: RazorpayOptions = {
      key,
      amount: options.amount,
      currency: options.currency || "INR",
      name: "Bus Booking AI Agent",
      description: `Bus Booking: ${options.bookingReference}`,
      order_id: options.orderId,
      prefill: {
        name: options.userName,
        email: options.userEmail,
      },
      theme: {
        color: "#16a34a", // Primary brand green
      },
      handler: (response: RazorpayPaymentSuccessResponse) => {
        resolved = true;
        resolve(response);
      },
      modal: {
        ondismiss: () => {
          if (!resolved) {
            reject(new Error("PAYMENT_DISMISSED"));
          }
        },
      },
    };

    try {
      const RazorpayConstructor = window.Razorpay;
      if (!RazorpayConstructor) {
        reject(new Error("Razorpay Checkout SDK is not available."));
        return;
      }
      const rzp = new RazorpayConstructor(rzpOptions);
      rzp.open();
    } catch (err) {
      reject(err);
    }
  });
}
