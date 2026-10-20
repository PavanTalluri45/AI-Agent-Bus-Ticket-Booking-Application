/**
 * Bus Agent Typed API Client
 *
 * Injects the Supabase access token in Authorization header.
 */

import { createClient } from "@/utils/supabase/client";
import type {
  ChatApiResponse,
  ConversationListResponse,
  ConversationDetailResponse,
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
  message: string,
  conversationId?: string,
): Promise<ChatApiResponse> {
  const headers = await getAuthHeader();

  const response = await fetch("/api/v1/chat", {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
    }),
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
  decision: "approve" | "reject",
  conversationId: string,
): Promise<ChatApiResponse> {
  const headers = await getAuthHeader();

  const response = await fetch("/api/v1/chat/approval", {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({
      approval_decision: decision,
      conversation_id: conversationId,
    }),
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
 * List conversations for the authenticated user with cursor pagination & search.
 */
export async function listConversations(params?: {
  cursor?: string | null;
  cursorId?: string | null;
  search?: string | null;
  limit?: number;
}): Promise<ConversationListResponse> {
  const headers = await getAuthHeader();

  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", params.limit.toString());
  if (params?.cursor) query.set("cursor", params.cursor);
  if (params?.cursorId) query.set("cursor_id", params.cursorId);
  if (params?.search && params.search.trim()) query.set("search", params.search.trim());

  const qs = query.toString();
  const url = `/api/v1/conversations${qs ? `?${qs}` : ""}`;

  const response = await fetch(url, {
    method: "GET",
    headers,
    credentials: "include",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Failed to fetch conversations (${response.status})`;
    throw new Error(errorMsg);
  }

  return data as ConversationListResponse;
}

/**
 * Retrieve conversation details, messages, and state for restore.
 */
export async function getConversation(
  conversationId: string,
): Promise<ConversationDetailResponse> {
  const headers = await getAuthHeader();

  const response = await fetch(`/api/v1/conversations/${conversationId}`, {
    method: "GET",
    headers,
    credentials: "include",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Failed to load conversation (${response.status})`;
    throw new Error(errorMsg);
  }

  return data as ConversationDetailResponse;
}

/**
 * Rename a conversation.
 */
export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<{ success: boolean; id: string; title: string }> {
  const headers = await getAuthHeader();

  const response = await fetch(`/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    headers,
    credentials: "include",
    body: JSON.stringify({ title }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Failed to rename conversation (${response.status})`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Delete a conversation.
 */
export async function deleteConversation(
  conversationId: string,
): Promise<{ success: boolean; id: string }> {
  const headers = await getAuthHeader();

  const response = await fetch(`/api/v1/conversations/${conversationId}`, {
    method: "DELETE",
    headers,
    credentials: "include",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg =
      data?.detail || data?.error || `Failed to delete conversation (${response.status})`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Verify Razorpay payment signature and finalize booking on the backend.
 */
export async function verifyPayment(
  payload: PaymentVerifyRequest,
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
