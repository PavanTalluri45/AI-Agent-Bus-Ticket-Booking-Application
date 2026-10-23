/**
 * Bus Agent Typed API Client
 *
 * Injects the Supabase access token in Authorization header.
 */

import { createClient } from "@/utils/supabase/client";
import type {
  AgentStep,
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

export type AgentStepHandler = (step: AgentStep) => void;

/**
 * Read an agent response.
 *
 * The backend streams Server-Sent Events:
 *   event: step   -> one agent step (passed to onStep as it arrives)
 *   event: final  -> the chat payload (this function resolves with it)
 *   event: error  -> {status, detail} (this function throws)
 *
 * Errors raised before streaming starts (401, 404, 429...) are plain JSON.
 */
async function readAgentResponse(
  response: Response,
  failureLabel: string,
  onStep?: AgentStepHandler,
): Promise<ChatApiResponse> {
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok || !contentType.includes("text/event-stream")) {
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMsg =
        data?.detail ||
        data?.error ||
        `${failureLabel} with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return data as ChatApiResponse;
  }

  if (!response.body) {
    throw new Error("The server returned an empty response stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const result: { final: ChatApiResponse | null } = { final: null };
  let buffer = "";

  const handleEvent = (rawEvent: string) => {
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (dataLines.length === 0) return;

    const data = JSON.parse(dataLines.join("\n"));

    if (eventName === "step") {
      onStep?.(data as AgentStep);
    } else if (eventName === "final") {
      result.final = data as ChatApiResponse;
    } else if (eventName === "error") {
      throw new Error(data?.detail || `${failureLabel}.`);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();

      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n");

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        handleEvent(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }

      if (done) break;
    }

    if (buffer.trim()) {
      handleEvent(buffer);
    }
  } finally {
    reader.cancel().catch(() => {});
  }

  if (!result.final) {
    throw new Error(
      "The connection closed before the agent finished. Please try again.",
    );
  }

  return result.final;
}

/**
 * Send a chat message to the LangGraph AI agent.
 * Agent steps are reported through onStep while the agent works.
 */
export async function sendChatMessage(
  message: string,
  conversationId?: string,
  onStep?: AgentStepHandler,
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

  return readAgentResponse(response, "Request failed", onStep);
}

/**
 * Submit an HITL approval decision (approve or reject) to resume the LangGraph flow.
 */
export async function sendApprovalDecision(
  decision: "approve" | "reject",
  conversationId: string,
  onStep?: AgentStepHandler,
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

  return readAgentResponse(response, "Approval failed", onStep);
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
