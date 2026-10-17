from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from bus_booking_ai_agent.config.database import engine

from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    run_agent,
)

from bus_booking_ai_agent.phase_05_memory.memory_service import (
    delete_memory,
    save_memory,
)

from bus_booking_ai_agent.phase_05_memory.memory_safety import (
    validate_memory_value,
)

from bus_booking_ai_agent.phase_06_security.rate_limiter import (
    check_rate_limit,
)

from bus_booking_ai_agent.auth import (
    AuthenticatedUser,
    get_current_user,
)

from bus_booking_ai_agent.services.booking_models import (
    CreatePaymentPendingBookingRequest,
)

from bus_booking_ai_agent.services.booking_service import (
    BookingCreationError,
    HoldExpiredError,
    HoldNotActiveError,
    HoldNotFoundError,
    HoldOwnershipError,
    create_payment_pending_booking,
)

from bus_booking_ai_agent.services.hold_models import (
    CreateHoldRequest,
)

from bus_booking_ai_agent.services.hold_service import (
    HoldConflictError,
    InvalidJourneySegmentError,
    ScheduleNotFoundError,
    ScheduleUnavailableError,
    SeatNotAvailableError,
    create_hold,
)

from bus_booking_ai_agent.services.payment_models import (
    CreatePaymentRequest,
    VerifyPaymentRequest,
)

from bus_booking_ai_agent.services.payment_service import (
    InvalidPaymentBookingStatusError,
    PaymentAlreadyProcessedError,
    PaymentBookingNotFoundError,
    PaymentBookingOwnershipError,
    PaymentError,
    PaymentNotFoundError,
    PaymentOrderMismatchError,
    PaymentOwnershipError,
    PaymentVerificationError,
    prepare_payment,
    verify_payment,
)

from bus_booking_ai_agent.services.razorpay_provider import (
    RazorpayProvider,
)

from bus_booking_ai_agent.services.booking_finalization_models import (
    BookingFinalizationError,
    finalize_booking,
)


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Bus Booking AI Agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Root
# ============================================================


@app.get("/")
async def read_root():
    """
    Basic health check for the FastAPI application.
    """

    return {
        "status": "ok",
        "service": "bus-booking-ai-agent",
    }


# ============================================================
# Authentication
# ============================================================


@app.get(
    "/api/v1/auth/me",
    response_model=AuthenticatedUser,
)
async def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Return the currently authenticated user.

    The identity comes from Supabase Auth through
    the verified access token.
    """

    return current_user


# ============================================================
# Development: Create Hold
# ============================================================


@app.post("/api/v1/dev/holds")
async def create_development_hold(
    request: CreateHoldRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Development endpoint used to verify the authenticated
    hold-creation workflow.

    This endpoint will later be replaced by the proper
    application booking flow.
    """

    try:
        hold = create_hold(
            current_user=current_user,
            schedule_id=request.schedule_id,
            seat_id=request.seat_id,
            boarding_stop_id=request.boarding_stop_id,
            dropping_stop_id=request.dropping_stop_id,
        )

        return {
            "success": True,
            "hold": hold,
        }

    except ScheduleNotFoundError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except ScheduleUnavailableError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except InvalidJourneySegmentError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except SeatNotAvailableError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except HoldConflictError as error:
        return {
            "success": False,
            "error": str(error),
        }


# ============================================================
# Development: Create PAYMENT_PENDING Booking
# ============================================================


@app.post("/api/v1/dev/bookings/payment-pending")
async def create_payment_pending_booking_endpoint(
    request: CreatePaymentPendingBookingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create a PAYMENT_PENDING booking from an existing
    authenticated user's active seat hold.

    The booking amount and journey information are
    determined by the backend and database.
    """

    try:
        result = create_payment_pending_booking(
            current_user=current_user,
            hold_id=request.hold_id,
            passenger_name=request.passenger_name,
            passenger_age=request.passenger_age,
            passenger_gender=request.passenger_gender,
        )

        return {
            "success": True,
            **result,
        }

    except HoldNotFoundError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except HoldOwnershipError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except HoldNotActiveError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except HoldExpiredError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except BookingCreationError as error:
        return {
            "success": False,
            "error": str(error),
        }


# ============================================================
# Development: Create Payment
# ============================================================


@app.post("/api/v1/dev/payments/create")
async def create_payment_endpoint(
    request: CreatePaymentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create a Razorpay order and application payment record
    for a PAYMENT_PENDING booking.

    The frontend provides only the booking ID.

    The backend determines:
    - authenticated user
    - booking ownership
    - booking status
    - payment amount
    - payment currency
    """

    try:
        provider = RazorpayProvider()

        result = prepare_payment(
            current_user=current_user,
            booking_id=request.booking_id,
            provider=provider,
        )

        return {
            "success": True,
            **result,
        }

    except PaymentBookingNotFoundError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentBookingOwnershipError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except InvalidPaymentBookingStatusError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentError as error:
        return {
            "success": False,
            "error": str(error),
        }


# ============================================================
# Development: Verify Payment
# ============================================================


class FinalizePaymentRequest(BaseModel):
    payment_id: UUID


GET_CONFIRMED_TICKET_SQL = """
SELECT
    b.booking_reference,
    b.status,
    b.total_amount,
    bs.passenger_name,
    bs.passenger_age,
    bs.passenger_gender,
    seat.seat_number,
    op.name AS operator_name,
    bus.bus_number,
    bus.bus_type,
    r.origin,
    r.destination,
    s.travel_date,
    b_stop.stop_name AS boarding_point,
    d_stop.stop_name AS dropping_point
FROM bookings b
LEFT JOIN booking_seats bs ON bs.booking_id = b.id
LEFT JOIN bus_seats seat ON seat.id = bs.seat_id
LEFT JOIN schedules s ON s.id = b.schedule_id
LEFT JOIN buses bus ON bus.id = s.bus_id
LEFT JOIN operators op ON op.id = bus.operator_id
LEFT JOIN routes r ON r.id = s.route_id
LEFT JOIN route_stops b_stop ON b_stop.id = b.boarding_stop_id
LEFT JOIN route_stops d_stop ON d_stop.id = b.dropping_stop_id
WHERE b.id = :booking_id
LIMIT 1;
"""


def _get_confirmed_ticket_details(booking_id: UUID) -> dict | None:
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(GET_CONFIRMED_TICKET_SQL),
                    {"booking_id": booking_id},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            data = dict(row)
            if data.get("total_amount") is not None:
                data["total_amount"] = str(data["total_amount"])
            if data.get("travel_date") is not None:
                data["travel_date"] = str(data["travel_date"])
            return data
    except Exception:
        return None


@app.post("/api/v1/dev/payments/verify")
@app.post("/api/v1/payment/verify")
async def verify_payment_endpoint(
    request: VerifyPaymentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Verify a Razorpay payment signature and finalize the booking.
    """

    try:
        provider = RazorpayProvider()

        result = verify_payment(
            current_user=current_user,
            payment_id=request.payment_id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_order_id=request.razorpay_order_id,
            razorpay_signature=request.razorpay_signature,
            provider=provider,
        )

        finalization = finalize_booking(
            current_user=current_user,
            payment_id=request.payment_id,
        )

        booking_id = finalization["booking"]["id"]
        ticket = _get_confirmed_ticket_details(booking_id)

        response_payload = {
            "success": True,
            **result,
            "finalization": finalization,
        }
        if ticket:
            response_payload["ticket"] = ticket

        return response_payload

    except PaymentNotFoundError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentOwnershipError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentAlreadyProcessedError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentOrderMismatchError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except PaymentVerificationError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except BookingFinalizationError as error:
        return {
            "success": False,
            "error": f"Payment verified but booking finalization failed: {error}",
        }

    except PaymentError as error:
        return {
            "success": False,
            "error": str(error),
        }


@app.post("/api/v1/dev/payments/finalize")
@app.post("/api/v1/payment/finalize")
async def finalize_payment_endpoint(
    request: FinalizePaymentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Finalize a booking after payment success.
    Transitions booking status to CONFIRMED and converts hold.
    """

    try:
        result = finalize_booking(
            current_user=current_user,
            payment_id=request.payment_id,
        )

        booking_id = result["booking"]["id"]
        ticket = _get_confirmed_ticket_details(booking_id)

        response_payload = {
            "success": True,
            **result,
        }
        if ticket:
            response_payload["ticket"] = ticket

        return response_payload

    except BookingFinalizationError as error:
        return {
            "success": False,
            "error": str(error),
        }


# ============================================================
# Agent Chat
# ============================================================


class AgentChatRequest(BaseModel):
    """Request body for a normal agent conversation message."""

    message: str = Field(min_length=1)


class AgentApprovalRequest(BaseModel):
    """Request body for resuming a pending human approval."""

    approval_decision: Literal["approve", "reject"]


class UpdateMemoryRequest(BaseModel):
    memory_type: str = Field(min_length=1)
    memory_key: str = Field(min_length=1)
    memory_value: str = Field(min_length=1)

    @field_validator("memory_value")
    @classmethod
    def validate_memory_value_field(
        cls,
        value: str,
    ) -> str:
        return validate_memory_value(value)


class DeleteMemoryRequest(BaseModel):
    memory_type: str = Field(min_length=1)
    memory_key: str = Field(min_length=1)


def _get_conversation_context(
    request: Request,
    response: Response,
    current_user: AuthenticatedUser,
) -> tuple[str, str]:
    """
    Get or create the browser conversation ID and build its LangGraph thread ID.

    The conversation ID is stored in an HttpOnly cookie. The authenticated
    Supabase user ID is always included in the LangGraph thread ID so one user
    cannot address another user's conversation thread.
    """

    conversation_id = request.cookies.get("bus_booking_conversation_id")

    if not conversation_id:
        conversation_id = str(uuid4())

        response.set_cookie(
            key="bus_booking_conversation_id",
            value=conversation_id,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )

    thread_id = f"{current_user.id}:{conversation_id}"

    return conversation_id, thread_id


def _check_agent_rate_limit(current_user: AuthenticatedUser) -> None:
    """Apply the agent chat rate limit to both normal and approval requests."""

    rate_limit = check_rate_limit(
        user_id=str(current_user.id),
        action="agent_chat",
        limit=10,
        window_seconds=60,
    )

    if not rate_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "Rate limit exceeded. Please wait before sending another request."
            ),
            headers={
                "Retry-After": str(rate_limit.retry_after_seconds),
            },
        )


# ============================================================
# Agent Chat: Normal Message
# ============================================================


@app.post("/api/v1/chat")
def chat_with_agent(
    request: Request,
    response: Response,
    chat_request: AgentChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Send a normal user message to the bus-booking AI agent.

    This endpoint is intentionally responsible only for normal conversation
    messages. Human approval is handled by /api/v1/chat/approval.
    """

    _check_agent_rate_limit(current_user)

    conversation_id, thread_id = _get_conversation_context(
        request=request,
        response=response,
        current_user=current_user,
    )

    try:
        result = run_agent(
            current_user=current_user,
            user_message=chat_request.message.strip(),
            thread_id=thread_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    response_payload = {
        "success": True,
        "conversation_id": conversation_id,
        "response": result["final_response"],
    }

    if result.get("__interrupt__"):
        response_payload["approval_required"] = True

    booking_ctx = result.get("booking_context", {})
    if booking_ctx.get("booking_id"):
        response_payload["booking"] = {
            "booking_id": booking_ctx.get("booking_id"),
            "booking_reference": booking_ctx.get("booking_reference"),
            "status": booking_ctx.get("booking_status"),
            "total_amount": booking_ctx.get("total_amount"),
        }
    if booking_ctx.get("payment_order_id"):
        response_payload["payment_order"] = {
            "payment_id": booking_ctx.get("payment_id"),
            "order_id": booking_ctx.get("payment_order_id"),
            "amount": booking_ctx.get("payment_order_amount"),
            "currency": booking_ctx.get("payment_currency"),
        }

    return response_payload


# ============================================================
# Agent Chat: Human Approval
# ============================================================


@app.post("/api/v1/chat/approval")
def approve_agent_action(
    request: Request,
    response: Response,
    approval_request: AgentApprovalRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Approve or reject a pending human-in-the-loop agent action.

    This endpoint must only be called after /api/v1/chat returns
    approval_required=true. It resumes the existing LangGraph thread and
    never starts a new conversation.
    """

    _check_agent_rate_limit(current_user)

    conversation_id = request.cookies.get("bus_booking_conversation_id")
    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="No active conversation thread found to approve. Start a booking flow first.",
        )

    thread_id = f"{current_user.id}:{conversation_id}"

    try:
        result = run_agent(
            current_user=current_user,
            user_message=approval_request.approval_decision,
            thread_id=thread_id,
            approval_decision=approval_request.approval_decision,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    response_payload = {
        "success": True,
        "conversation_id": conversation_id,
        "response": result["final_response"],
    }

    if result.get("__interrupt__"):
        response_payload["approval_required"] = True

    booking_ctx = result.get("booking_context", {})
    if booking_ctx.get("booking_id"):
        response_payload["booking"] = {
            "booking_id": booking_ctx.get("booking_id"),
            "booking_reference": booking_ctx.get("booking_reference"),
            "status": booking_ctx.get("booking_status"),
            "total_amount": booking_ctx.get("total_amount"),
        }
    if booking_ctx.get("payment_order_id"):
        response_payload["payment_order"] = {
            "payment_id": booking_ctx.get("payment_id"),
            "order_id": booking_ctx.get("payment_order_id"),
            "amount": booking_ctx.get("payment_order_amount"),
            "currency": booking_ctx.get("payment_currency"),
        }

    return response_payload


# ============================================================
# Memory: Update User Memory
# ============================================================


@app.post("/api/v1/memory")
async def update_user_memory(
    request: UpdateMemoryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create or update a memory for the authenticated user.

    The client never supplies the user ID.
    The authenticated Supabase user ID is used as the memory owner.
    """

    memory = save_memory(
        user_id=str(current_user.id),
        memory_type=request.memory_type,
        memory_key=request.memory_key,
        memory_value=request.memory_value,
    )

    return {
        "success": True,
        "memory": memory,
    }


# ============================================================
# Memory: Delete User Memory
# ============================================================


@app.delete("/api/v1/memory")
async def delete_user_memory(
    request: DeleteMemoryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Delete a memory belonging to the authenticated user.

    The client never supplies the user ID.
    The authenticated Supabase user ID determines ownership.
    """

    deleted = delete_memory(
        user_id=str(current_user.id),
        memory_type=request.memory_type,
        memory_key=request.memory_key,
    )

    return {
        "success": True,
        "deleted": deleted,
    }