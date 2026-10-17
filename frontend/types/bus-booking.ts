/**
 * Types for the Bus Booking AI Agent Frontend
 */

export interface BookingSummary {
  booking_id: string;
  booking_reference: string;
  status: string;
  total_amount: string;
}

export interface PaymentOrderSummary {
  payment_id: string;
  order_id: string;
  amount: number; // in paise (e.g. 125000 = ₹1250.00)
  currency: string;
}

export interface ConfirmedTicketData {
  booking_reference: string;
  status: string;
  total_amount: string;
  operator_name?: string;
  bus_number?: string;
  bus_type?: string;
  seat_number?: string;
  passenger_name?: string;
  passenger_age?: number;
  passenger_gender?: string;
  origin?: string;
  destination?: string;
  travel_date?: string;
  boarding_point?: string;
  dropping_point?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  approvalRequired?: boolean;
  booking?: BookingSummary;
  paymentOrder?: PaymentOrderSummary;
  confirmedTicket?: ConfirmedTicketData;
}

export interface ChatApiRequest {
  message: string;
}

export interface ChatApiResponse {
  success: boolean;
  conversation_id?: string;
  response?: string;
  approval_required?: boolean;
  booking?: BookingSummary;
  payment_order?: PaymentOrderSummary;
  error?: string;
}

export interface ApprovalDecisionRequest {
  approval_decision: "approve" | "reject";
}

export interface PaymentVerifyRequest {
  payment_id: string;
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface PaymentVerifyResponse {
  success: boolean;
  booking_id?: string;
  payment?: {
    id: string;
    booking_id: string;
    provider: string;
    provider_order_id: string;
    provider_payment_id: string;
    amount: string;
    currency: string;
    status: string;
  };
  finalization?: {
    booking: {
      id: string;
      booking_reference: string;
      auth_user_id: string;
      schedule_id: string;
      status: string;
      total_amount: string;
      passenger_count: number;
    };
    hold: {
      id: string;
      status: string;
      booking_id: string;
    };
    payment_id: string;
  };
  ticket?: ConfirmedTicketData;
  error?: string;
}

export interface RazorpayResponsePayload {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: RazorpayResponsePayload) => void;
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

export interface RazorpayInstance {
  open: () => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}

