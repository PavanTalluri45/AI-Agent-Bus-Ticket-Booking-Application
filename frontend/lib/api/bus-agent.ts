/**
 * Bus Agent Typed API Client
 *
 * Uses credentials: "include" so the HttpOnly bus_booking_conversation_id cookie
 * is persisted and transmitted, and injects the Supabase access token in Authorization header.
 */

import { createClient } from "@/utils/supabase/client";
import type {
  ChatApiResponse,
  PaymentVerifyRequest,
  PaymentVerifyResponse,
} from "@/types/bus-booking";

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("You must be signed in to perform this action.");
  }

  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

/**
 * Send a chat message to the LangGraph AI agent.
 */
export async function sendChatMessage(
  message: string
): Promise<ChatApiResponse> {
  const headers = await getAuthHeader();

  const response = await fetch("/api/v1/chat", {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({ message }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Request failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return data as ChatApiResponse;
}

/**
 * Submit an HITL approval decision (approve or reject) to resume the LangGraph flow.
 */
export async function sendApprovalDecision(
  decision: "approve" | "reject"
): Promise<ChatApiResponse> {
  const headers = await getAuthHeader();

  const response = await fetch("/api/v1/chat/approval", {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({ approval_decision: decision }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Approval failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return data as ChatApiResponse;
}

/**
 * Verify Razorpay payment signature and finalize booking on the backend.
 */
export async function verifyPayment(
  payload: PaymentVerifyRequest
): Promise<PaymentVerifyResponse> {
  const headers = await getAuthHeader();

  const response = await fetch("/api/v1/payment/verify", {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || !data?.success) {
    const errorMsg =
      data?.error || data?.detail || "Payment verification failed on the server.";
    throw new Error(errorMsg);
  }

  return data as PaymentVerifyResponse;
}

