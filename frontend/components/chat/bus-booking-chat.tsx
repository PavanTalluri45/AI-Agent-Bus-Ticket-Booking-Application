"use client";

import React, { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useConversationsContext } from "@/context/ConversationsContext";
import {
  sendChatMessage,
  sendApprovalDecision,
  verifyPayment,
  getConversation,
} from "@/lib/api/bus-agent";
import { openRazorpayCheckout } from "@/lib/razorpay";
import { ApprovalCard } from "./approval-card";
import { PaymentCard } from "./payment-card";
import { ConfirmedTicket } from "./confirmed-ticket";
import { AgentSteps } from "./agent-steps";
import { SeatMap } from "./seat-map";
import { SelectionOptions } from "./selection-options";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import {
  ArrowUp,
  Loader2,
  AlertCircle,
} from "lucide-react";
import type {
  AgentStep,
  ChatMessage,
  BookingSummary,
  PaymentOrderSummary,
  ConfirmedTicketData,
} from "@/types/bus-booking";

// Insert a streamed step, or replace the earlier event with the same ID.
function upsertStep(steps: AgentStep[], step: AgentStep) {
  const index = steps.findIndex((s) => s.id === step.id);
  if (index === -1) {
    steps.push(step);
  } else {
    steps[index] = step;
  }
}

export interface BusBookingChatProps {
  conversationId?: string;
}

export function BusBookingChat({ conversationId: initialConversationId }: BusBookingChatProps) {
  const { user } = useAuth();
  const router = useRouter();
  const { refresh } = useConversationsContext();

  // Active Conversation ID
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId || null,
  );
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(
    Boolean(initialConversationId),
  );

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([]);

  // HITL Approval State
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  // Payment State
  const [activeBooking, setActiveBooking] = useState<BookingSummary | null>(
    null,
  );
  const [paymentOrder, setPaymentOrder] = useState<PaymentOrderSummary | null>(
    null,
  );
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  // Confirmed Ticket State
  const [confirmedTicket, setConfirmedTicket] =
    useState<ConfirmedTicketData | null>(null);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Restore conversation if an initial conversationId is provided
  useEffect(() => {
    if (!initialConversationId) return;

    let isMounted = true;

    getConversation(initialConversationId)
      .then((data) => {
        if (!isMounted) return;
        if (data.success) {
          setConversationId(data.id);

          const loadedMessages: ChatMessage[] = data.messages.map((m) => {
            const timeStr = m.created_at
              ? new Date(m.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "";

            return {
              id: m.id,
              role: m.role,
              content: m.content,
              timestamp: timeStr,
              approvalRequired: m.metadata?.approval_required,
              booking: m.metadata?.booking,
              paymentOrder: m.metadata?.payment_order,
              confirmedTicket: m.metadata?.confirmed_ticket,
              seatMap: m.metadata?.seat_map,
              options: m.metadata?.options,
              selectedSeat: m.metadata?.selected_seat,
              steps: m.metadata?.steps,
            };
          });

          if (data.confirmed_ticket) {
            const confirmationMessage: ChatMessage = {
              id: `confirmed-${data.confirmed_ticket.booking_reference}`,
              role: "assistant",
              content:
                "Payment verified successfully! Your bus ticket has been confirmed. You can see your complete ticket details below.",
              timestamp: "",
              confirmedTicket: data.confirmed_ticket,
            };
            const existingTicketIndex = loadedMessages.findIndex(
              (message) =>
                message.confirmedTicket?.booking_reference ===
                data.confirmed_ticket?.booking_reference,
            );
            const existingConfirmationIndex = loadedMessages.findIndex(
              (message) =>
                message.content.includes("Payment verified successfully"),
            );
            if (existingTicketIndex >= 0 || existingConfirmationIndex >= 0) {
              const confirmationIndex =
                existingTicketIndex >= 0
                  ? existingTicketIndex
                  : existingConfirmationIndex;
              loadedMessages[confirmationIndex] = {
                ...loadedMessages[confirmationIndex],
                confirmedTicket: data.confirmed_ticket,
              };
            } else {
              const bookingMessageIndex = loadedMessages.findIndex(
                (message) =>
                  message.booking?.booking_reference ===
                  data.confirmed_ticket?.booking_reference,
              );
              loadedMessages.splice(
                bookingMessageIndex >= 0
                  ? bookingMessageIndex + 1
                  : loadedMessages.length,
                0,
                confirmationMessage,
              );
            }
            setConfirmedTicket(data.confirmed_ticket);
          } else {
            setConfirmedTicket(null);
          }

          setMessages(loadedMessages);

          // Restore pending approval if active in LangGraph
          if (data.pending_approval) {
            setApprovalRequired(true);
            setPendingPrompt(data.pending_approval.prompt);
          } else {
            setApprovalRequired(false);
            setPendingPrompt(null);
          }

          // Restore pending payment order if active & valid
          if (data.pending_payment_order) {
            setPaymentOrder(data.pending_payment_order.payment_order);
            setActiveBooking(data.pending_payment_order.booking);
          } else {
            setPaymentOrder(null);
            setActiveBooking(null);
          }

        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Failed to load conversation history.",
        );
      })
      .finally(() => {
        if (isMounted) setIsInitialLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [initialConversationId]);

  const scrollToBottom = () => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth",
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [
    messages,
    liveSteps,
    approvalRequired,
    paymentOrder,
    confirmedTicket,
    isLoading,
    isVerifying,
  ]);

  // Handle automatic checkout opening when a new payment_order arrives
  const triggerRazorpayCheckout = async (
    order: PaymentOrderSummary,
    booking?: BookingSummary,
  ) => {
    if (isPaymentOpen || isVerifying) return;

    setIsPaymentOpen(true);
    setErrorMessage(null);

    try {
      const response = await openRazorpayCheckout({
        orderId: order.order_id,
        amount: order.amount,
        currency: order.currency,
        bookingReference: booking?.booking_reference || "BUS-TICKET",
        userName: user?.user_metadata?.full_name || user?.email || undefined,
        userEmail: user?.email || undefined,
      });

      // User paid in Razorpay modal - now verify with server
      setIsPaymentOpen(false);
      setIsVerifying(true);

      const verificationResult = await verifyPayment({
        payment_id: order.payment_id,
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_order_id: response.razorpay_order_id,
        razorpay_signature: response.razorpay_signature,
      });

      // Authoritative verification succeeded
      setIsVerifying(false);

      const ticket =
        verificationResult.ticket ??
        (verificationResult.finalization?.booking
          ? {
          booking_reference:
            verificationResult.finalization.booking.booking_reference,
          status: verificationResult.finalization.booking.status,
          total_amount: verificationResult.finalization.booking.total_amount,
            }
          : null);
      setConfirmedTicket(ticket);

      // Clear pending payment order once confirmed
      setPaymentOrder(null);

      // Append assistant confirmation message
      setMessages((prev) => [
        ...prev,
        {
          id: `confirmed-${Date.now()}`,
          role: "assistant",
          content:
            "Payment verified successfully! Your bus ticket has been confirmed. You can see your complete ticket details below.",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          confirmedTicket: ticket || undefined,
        },
      ]);
    } catch (err: unknown) {
      setIsPaymentOpen(false);
      setIsVerifying(false);

      const error = err as Error;
      if (error?.message === "PAYMENT_DISMISSED") {
        setMessages((prev) => [
          ...prev,
          {
            id: `dismissed-${Date.now()}`,
            role: "assistant",
            content:
              "Payment checkout was closed before completion. Your seat reservation is still active. You can reopen checkout using the button above when you are ready to pay.",
            timestamp: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
          },
        ]);
      } else {
        setErrorMessage(
          error?.message || "Payment process encountered an error.",
        );
      }
    }
  };

  // Collects the steps streamed during one request and shows them live.
  const startStepCollector = () => {
    const collected: AgentStep[] = [];
    setLiveSteps([]);

    const onStep = (step: AgentStep) => {
      upsertStep(collected, step);
      setLiveSteps([...collected]);
    };

    return { collected, onStep };
  };

  // 1. Send normal user chat message
  const sendMessage = async (messageText: string) => {
    const text = messageText.trim();
    if (
      !text ||
      isLoading ||
      approvalRequired ||
      isPaymentOpen ||
      isVerifying ||
      isInitialLoading
    ) {
      return;
    }

    setInputValue("");
    setErrorMessage(null);

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const { collected, onStep } = startStepCollector();
      const data = await sendChatMessage(
        text,
        conversationId || undefined,
        onStep,
      );

      // Seamlessly update URL on message 1 without unmounting component!
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id);
        window.history.replaceState({}, "", `/chat/${data.conversation_id}`);
        // Refresh sidebar immediately
        refresh();
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response || "I am processing your request.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        approvalRequired: data.approval_required,
        booking: data.booking,
        paymentOrder: data.payment_order,
        seatMap: data.seat_map,
        options: data.options,
        selectedSeat: data.selected_seat,
        steps: collected.length > 0 ? collected : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLiveSteps([]);

      if (data.approval_required) {
        setApprovalRequired(true);
        setPendingPrompt(data.response || "Do you approve this action?");
      } else {
        setApprovalRequired(false);
        setPendingPrompt(null);
      }

      if (data.booking) {
        setActiveBooking(data.booking);
      }

      if (data.payment_order) {
        setPaymentOrder(data.payment_order);
        await triggerRazorpayCheckout(data.payment_order, data.booking);
      }
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(
        error?.message || "Failed to communicate with the bus agent.",
      );
    } finally {
      setLiveSteps([]);
      setIsLoading(false);
    }
  };

  const handleSendMessage = (e?: React.FormEvent) => {
    e?.preventDefault();
    void sendMessage(inputValue);
  };

  // 2. Handle HITL Approve
  const handleApprove = async () => {
    if (!conversationId) {
      setErrorMessage("No active conversation found to approve.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const { collected, onStep } = startStepCollector();
      const data = await sendApprovalDecision(
        "approve",
        conversationId,
        onStep,
      );

      setApprovalRequired(false);
      setPendingPrompt(null);

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response || "Action approved.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        booking: data.booking,
        paymentOrder: data.payment_order,
        steps: collected.length > 0 ? collected : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLiveSteps([]);

      if (data.booking) {
        setActiveBooking(data.booking);
      }

      if (data.payment_order) {
        setPaymentOrder(data.payment_order);
        await triggerRazorpayCheckout(data.payment_order, data.booking);
      }
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(error?.message || "Approval submission failed.");
    } finally {
      setLiveSteps([]);
      setIsLoading(false);
    }
  };

  // 3. Handle HITL Reject
  const handleReject = async () => {
    if (!conversationId) {
      setErrorMessage("No active conversation found to reject.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const { collected, onStep } = startStepCollector();
      const data = await sendApprovalDecision(
        "reject",
        conversationId,
        onStep,
      );

      setApprovalRequired(false);
      setPendingPrompt(null);

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response || "Action rejected.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        steps: collected.length > 0 ? collected : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLiveSteps([]);
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(error?.message || "Rejection submission failed.");
    } finally {
      setLiveSteps([]);
      setIsLoading(false);
    }
  };

  const handleBookAnother = () => {
    router.push("/chat");
  };

  const isInputDisabled =
    isLoading || approvalRequired || isPaymentOpen || isVerifying || isInitialLoading;
  // The seat map is shown once, in the response that checked availability.
  let newestSeatMapCandidateIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].seatMap) {
      newestSeatMapCandidateIndex = i;
      break;
    }
  }
  let newestOptionsIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].options) {
      newestOptionsIndex = i;
      break;
    }
  }
  const newestOptionsMessage =
    newestOptionsIndex >= 0 ? messages[newestOptionsIndex] : undefined;
  const newestSeatMapIndex =
    newestSeatMapCandidateIndex > newestOptionsIndex
      ? newestSeatMapCandidateIndex
      : -1;
  const newestSeatMapMessage =
    newestSeatMapIndex >= 0 ? messages[newestSeatMapIndex] : undefined;
  const laterMessages =
    newestSeatMapIndex >= 0 ? messages.slice(newestSeatMapIndex + 1) : [];
  // Once the hold, booking or payment step starts, the map stops being clickable.
  const seatMapLocked = Boolean(
    approvalRequired ||
      activeBooking ||
      paymentOrder ||
      confirmedTicket ||
      laterMessages.some(
        (m) =>
          m.approvalRequired ||
          m.booking ||
          m.paymentOrder ||
          m.confirmedTicket,
      ),
  );
  // The seat the application actually resolved, taken from the latest response.
  let resolvedSeat: string | null | undefined;
  for (let i = messages.length - 1; i > newestSeatMapIndex; i--) {
    if (messages[i].role === "assistant" && messages[i].selectedSeat !== undefined) {
      resolvedSeat = messages[i].selectedSeat;
      break;
    }
  }

  const displayName =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split("@")[0] ||
    "there";

  const handleSuggestion = (from: string, to: string) => {
    const today = new Date().toLocaleDateString("en-CA");
    setInputValue(`Find buses from ${from} to ${to} on ${today}`);
    inputRef.current?.focus();
  };

  const userAvatar =
    user?.user_metadata?.avatar_url || user?.user_metadata?.picture || "";
  const userInitial = (user ? displayName : "U").charAt(0).toUpperCase();

  if (isInitialLoading) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center max-w-4xl mx-auto w-full gap-3 text-muted-foreground text-sm">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span>Loading conversation</span>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col max-w-4xl mx-auto w-full">
      {/* Empty (initial) state */}
      {messages.length === 0 ? (
        <Empty className="min-h-0">
          <EmptyHeader>
            <EmptyTitle className="text-[36px] leading-[40px] bg-gradient-to-r from-[rgb(81,175,230)] via-[rgb(53,95,242)] to-[rgb(17,40,122)] bg-clip-text text-transparent">
              Hi, {displayName}
            </EmptyTitle>
            <EmptyDescription>
              Tell the agent your route and date. It will search buses, help you
              pick a seat and take you through secure payment.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent className="max-w-xl">
            <div className="mx-auto flex w-fit max-w-full flex-col gap-3">
              <p className="text-sm font-medium text-muted-foreground">
                You may try asking
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {[
                  { from: "Hyderabad", to: "Bangalore" },
                  { from: "Hyderabad", to: "Vijayawada" },
                  { from: "Bangalore", to: "Chennai" },
                ].map((route) => (
                  <Button
                    key={`${route.from}-${route.to}`}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="sm:last:odd:col-span-2 sm:last:odd:justify-self-center"
                    onClick={() => handleSuggestion(route.from, route.to)}
                  >
                    Buses From {route.from} to {route.to}
                  </Button>
                ))}
              </div>
            </div>
          </EmptyContent>
        </Empty>
      ) : (
        <div
          ref={messagesContainerRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth py-4 space-y-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex items-start gap-2.5 sm:gap-3 ${
                  isUser ? "flex-row-reverse" : "flex-row"
                }`}
              >
                {isUser ? (
                  <Avatar className="mt-1 size-7 shrink-0 sm:size-8">
                    <AvatarImage
                      src={userAvatar}
                      alt={displayName}
                      referrerPolicy="no-referrer"
                    />
                    <AvatarFallback className="text-xs">
                      {userInitial}
                    </AvatarFallback>
                  </Avatar>
                ) : (
                  <Image
                    src="/ai-agent.webp"
                    alt="AI agent"
                    width={32}
                    height={32}
                    className="size-7 shrink-0 rounded-full sm:size-8"
                  />
                )}

                <div
                  className={`flex flex-col ${
                    msg.confirmedTicket
                      ? "w-full max-w-full"
                      : "max-w-[85%] sm:max-w-[78%]"
                  } ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  {!isUser && msg.steps && msg.steps.length > 0 && (
                    <div className="mb-1.5 min-w-0 max-w-full">
                      <AgentSteps steps={msg.steps} />
                    </div>
                  )}
                  <div
                    className={`text-sm whitespace-pre-wrap leading-relaxed ${
                      isUser
                        ? "rounded-[22px] bg-primary px-4 py-2.5 text-primary-foreground shadow-sm"
                        : "py-1.5 text-foreground"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {!isUser && msg.id === newestSeatMapMessage?.id && msg.seatMap && (
                    <>
                      <SeatMap
                        key={
                          resolvedSeat ??
                          msg.seatMap.selected_seat ??
                          "unselected"
                        }
                        data={msg.seatMap}
                        selectedSeat={resolvedSeat}
                        locked={seatMapLocked}
                        interactive={!seatMapLocked && !isInputDisabled}
                        onSelectSeat={(seatNumber) => {
                          void sendMessage(`I want seat ${seatNumber}`);
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        disabled={seatMapLocked || isInputDisabled}
                        onClick={() => void sendMessage("Change stops")}
                      >
                        Change stops
                      </Button>
                    </>
                  )}
                  {!isUser &&
                    msg.id === newestOptionsMessage?.id &&
                    msg.options && (
                      <SelectionOptions
                        options={msg.options}
                        interactive={
                          newestOptionsIndex === messages.length - 1 &&
                          !isInputDisabled
                        }
                        onSelect={(label) => void sendMessage(label)}
                        onContinue={(boarding, dropping) => {
                          void sendMessage(
                            `Boarding stop: ${boarding.label}, Dropping stop: ${dropping.label}`,
                          );
                        }}
                      />
                    )}
                  {msg.timestamp && (
                    <span className="text-[10px] text-muted-foreground mt-1 px-1">
                      {msg.timestamp}
                    </span>
                  )}
                  {!isUser && msg.confirmedTicket && (
                    <ConfirmedTicket
                      ticket={msg.confirmedTicket}
                      onBookAnother={handleBookAnother}
                    />
                  )}
                </div>
              </div>
            );
          })}

          {/* HITL Approval Barrier Card */}
          {approvalRequired && pendingPrompt && (
            <div className="pl-9 sm:pl-11 pr-2">
              <ApprovalCard
                prompt={pendingPrompt}
                onApprove={handleApprove}
                onReject={handleReject}
                disabled={isLoading}
              />
            </div>
          )}

          {/* Active Payment Order Card */}
          {paymentOrder && !confirmedTicket && (
            <div className="pl-9 sm:pl-11 pr-2">
              <PaymentCard
                paymentOrder={paymentOrder}
                booking={activeBooking || undefined}
                isPaymentOpen={isPaymentOpen}
                isVerifying={isVerifying}
                onOpenCheckout={() =>
                  triggerRazorpayCheckout(
                    paymentOrder,
                    activeBooking || undefined,
                  )
                }
                disabled={isLoading || isVerifying}
              />
            </div>
          )}

          {/* Assistant Typing Indicator */}
          {isLoading && liveSteps.length > 0 && (
            <div className="flex items-start gap-2.5 sm:gap-3">
              <Image
                src="/ai-agent.webp"
                alt="AI agent"
                width={32}
                height={32}
                className="mt-0.5 size-7 shrink-0 rounded-full sm:size-8"
              />
              <div className="min-w-0 max-w-[85%] py-1.5 sm:max-w-[78%]">
                <AgentSteps steps={liveSteps} streaming />
              </div>
            </div>
          )}

          {isLoading && liveSteps.length === 0 && (
            <div className="flex items-center gap-2.5 text-xs text-muted-foreground pl-1">
              <Image
                src="/ai-agent.webp"
                alt="AI agent"
                width={28}
                height={28}
                className="size-7 shrink-0 animate-pulse rounded-full"
              />
            </div>
          )}

          {/* Error Alert Banner */}
          {errorMessage && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 text-destructive rounded-lg text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span className="flex-1">{errorMessage}</span>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={() => setErrorMessage(null)}
                className="text-xs h-6 px-1.5"
              >
                Dismiss
              </Button>
            </div>
          )}

        </div>
      )}

      {/* Input Form Bar */}
      <div className="shrink-0 pt-2 sm:pt-3 pb-1 sm:pb-2">
        <form ref={formRef} onSubmit={handleSendMessage}>
          <InputGroup>
            <InputGroupTextarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={
                approvalRequired
                  ? "Please approve or reject above before continuing..."
                  : isVerifying
                    ? "Verifying payment with server..."
                    : isPaymentOpen
                      ? "Complete payment in Razorpay modal..."
                      : "Type your message"
              }
              disabled={isInputDisabled}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  formRef.current?.requestSubmit();
                }
              }}
              rows={1}
              className="max-h-32 min-h-0 px-3 py-2.5 text-sm"
            />
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                type="submit"
                size="icon-sm"
                variant="default"
                className="rounded-full"
                disabled={isInputDisabled || !inputValue.trim()}
                aria-label="Send message"
              >
                {isLoading ? <Loader2 className="animate-spin" /> : <ArrowUp />}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </div>
    </div>
  );
}
