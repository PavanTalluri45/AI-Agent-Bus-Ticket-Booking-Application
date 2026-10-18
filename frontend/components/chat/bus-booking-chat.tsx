"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  sendChatMessage,
  sendApprovalDecision,
  verifyPayment,
} from "@/lib/api/bus-agent";
import { openRazorpayCheckout } from "@/lib/razorpay";
import { ApprovalCard } from "./approval-card";
import { PaymentCard } from "./payment-card";
import { ConfirmedTicket } from "./confirmed-ticket";
import { Button } from "@/components/ui/button";
import {
  Empty,
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
  Bot,
  User,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import type {
  ChatMessage,
  BookingSummary,
  PaymentOrderSummary,
  ConfirmedTicketData,
} from "@/types/bus-booking";

export function BusBookingChat() {
  const { user } = useAuth();

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [
    messages,
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

      if (verificationResult.ticket) {
        setConfirmedTicket(verificationResult.ticket);
      } else if (verificationResult.finalization?.booking) {
        setConfirmedTicket({
          booking_reference:
            verificationResult.finalization.booking.booking_reference,
          status: verificationResult.finalization.booking.status,
          total_amount: verificationResult.finalization.booking.total_amount,
        });
      }

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
        },
      ]);
    } catch (err: unknown) {
      setIsPaymentOpen(false);
      setIsVerifying(false);

      const error = err as Error;
      if (error?.message === "PAYMENT_DISMISSED") {
        // Modal dismissed by user without paying - not an API failure
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

  // 1. Send normal user chat message
  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const text = inputValue.trim();
    if (
      !text ||
      isLoading ||
      approvalRequired ||
      isPaymentOpen ||
      isVerifying
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
      const data = await sendChatMessage(text);

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
      };

      setMessages((prev) => [...prev, assistantMessage]);

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
        // Automatically open checkout
        await triggerRazorpayCheckout(data.payment_order, data.booking);
      }
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(
        error?.message || "Failed to communicate with the bus agent.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Handle HITL Approve
  const handleApprove = async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await sendApprovalDecision("approve");

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
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (data.booking) {
        setActiveBooking(data.booking);
      }

      if (data.payment_order) {
        setPaymentOrder(data.payment_order);
        // Automatically open checkout upon booking approval
        await triggerRazorpayCheckout(data.payment_order, data.booking);
      }
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(error?.message || "Approval submission failed.");
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Handle HITL Reject
  const handleReject = async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await sendApprovalDecision("reject");

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
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(error?.message || "Rejection submission failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleBookAnother = () => {
    setConfirmedTicket(null);
    setPaymentOrder(null);
    setActiveBooking(null);
    setApprovalRequired(false);
    setPendingPrompt(null);
    setMessages((prev) => [
      ...prev,
      {
        id: `new-search-${Date.now()}`,
        role: "assistant",
        content:
          "Where would you like to travel next? Please enter your origin, destination, and travel date.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);
  };

  const isInputDisabled =
    isLoading || approvalRequired || isPaymentOpen || isVerifying;



  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-4xl mx-auto w-full">
      {/* Empty (initial) state */}
      {messages.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>Where would you like to travel?</EmptyTitle>
            <EmptyDescription>
              Tell the agent your route and date. It will search buses, help you
              pick a seat and take you through secure payment.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex items-start gap-2.5 sm:gap-3 ${
                  isUser ? "flex-row-reverse" : "flex-row"
                }`}
              >
                <div
                  className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-medium ${
                    isUser
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground border"
                  }`}
                >
                  {isUser ? (
                    <User className="w-4 h-4" />
                  ) : (
                    <Bot className="w-4 h-4" />
                  )}
                </div>

                <div
                  className={`flex flex-col max-w-[85%] sm:max-w-[78%] ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed shadow-sm ${
                      isUser
                        ? "bg-primary text-primary-foreground rounded-tr-xs"
                        : "bg-muted/70 dark:bg-muted/40 text-foreground border rounded-tl-xs"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.timestamp && (
                    <span className="text-[10px] text-muted-foreground mt-1 px-1">
                      {msg.timestamp}
                    </span>
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

          {/* Confirmed Ticket Card */}
          {confirmedTicket && (
            <div className="pl-9 sm:pl-11 pr-2">
              <ConfirmedTicket
                ticket={confirmedTicket}
                onBookAnother={handleBookAnother}
              />
            </div>
          )}

          {/* Assistant Typing Indicator */}
          {isLoading && (
            <div className="flex items-center gap-2.5 text-xs text-muted-foreground pl-1">
              <div className="w-7 h-7 rounded-full bg-muted border flex items-center justify-center">
                <Bot className="w-4 h-4 animate-pulse text-muted-foreground" />
              </div>
              <div className="flex items-center gap-1.5 bg-muted/50 border px-3 py-1.5 rounded-full">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600 animate-spin" />
                <span>Agent is thinking</span>
              </div>
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

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input Form Bar */}
      <div className="pt-3 sm:pt-4">
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
                      : "Type your message (e.g. 'I want seat 1B', 'Search buses to Chennai')..."
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
              className="p-3 text-sm"
            />
            <InputGroupAddon align="block-end">
              <InputGroupButton
                type="submit"
                size="icon-sm"
                variant="default"
                className="ml-auto rounded-full"
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
