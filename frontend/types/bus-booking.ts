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
  boarding_time?: string;
  boarding_day_offset?: number;
  dropping_time?: string;
  dropping_day_offset?: number;
}

export type SelectionOptionsKind = "bus" | "stops";

export interface BusSelectionOptionItem {
  label: string;
  detail: string;
}

export interface StopSelectionOptionItem {
  label: string;
  display_time: string;
  sequence_number: number;
  selected?: boolean;
}

export type SelectionOptionsData =
  | {
      kind: "bus";
      items: BusSelectionOptionItem[];
    }
  | {
      kind: "stops";
      boarding: StopSelectionOptionItem[];
      dropping: StopSelectionOptionItem[];
    };

export type SeatStatus = "available" | "unavailable" | "held_by_you";

export interface SeatMapSeat {
  seat_number: string;
  seat_type: string;
  row_number: number | null;
  column_number: number | null;
  status: SeatStatus;
}

export interface SeatMapData {
  bus_type: string | null;
  selected_seat: string | null;
  seats: SeatMapSeat[];
}

export type AgentStepStatus = "running" | "done" | "error";

/**
 * One live step the agent reports while it works (thinking, calling a tool,
 * holding a seat...). The backend sends the same step ID several times as it
 * changes from "running" to "done" or "error"; the latest event wins.
 */
export interface AgentStep {
  id: string;
  title: string;
  status: AgentStepStatus;
  description?: string;
  duration_ms?: number;
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
  seatMap?: SeatMapData;
  options?: SelectionOptionsData;
  /** Seat the application resolved; undefined when the response carried none. */
  selectedSeat?: string | null;
  steps?: AgentStep[];
}

export interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    approval_required?: boolean;
    booking?: BookingSummary;
    payment_order?: PaymentOrderSummary;
    confirmed_ticket?: ConfirmedTicketData;
    seat_map?: SeatMapData;
    options?: SelectionOptionsData;
    selected_seat?: string | null;
    steps?: AgentStep[];
  } | null;
  created_at: string;
}

export interface ConversationListItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  success: boolean;
  conversations: ConversationListItem[];
  next_cursor: string | null;
  next_cursor_id: string | null;
  has_more: boolean;
}

export interface ConversationDetailResponse {
  success: boolean;
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: StoredChatMessage[];
  pending_approval: { prompt: string } | null;
  pending_payment_order: {
    payment_order: PaymentOrderSummary;
    booking: BookingSummary;
  } | null;
  confirmed_ticket: ConfirmedTicketData | null;
  error?: string;
}

export interface ChatApiRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatApiResponse {
  success: boolean;
  conversation_id?: string;
  response?: string;
  approval_required?: boolean;
  booking?: BookingSummary;
  payment_order?: PaymentOrderSummary;
  seat_map?: SeatMapData;
  options?: SelectionOptionsData;
  selected_seat?: string | null;
  error?: string;
}

export interface ApprovalDecisionRequest {
  approval_decision: "approve" | "reject";
  conversation_id: string;
}

export interface RenameConversationRequest {
  title: string;
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