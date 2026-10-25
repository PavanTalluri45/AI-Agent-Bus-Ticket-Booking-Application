import json
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.config.gemini import client as gemini_client, MODEL as GEMINI_MODEL

from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    checkpointer,
    graph,
    run_agent,
)

from bus_booking_ai_agent.phase_04_langgraph.step_events import (
    reset_step_emitter,
    set_step_emitter,
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
# Agent Chat & Conversation Management
# ============================================================


class AgentChatRequest(BaseModel):
    """Request body for an agent conversation message."""

    message: str = Field(min_length=1)
    conversation_id: str | None = None


class AgentApprovalRequest(BaseModel):
    """Request body for resuming a pending human approval."""

    approval_decision: Literal["approve", "reject"]
    conversation_id: str | None = None


class RenameConversationRequest(BaseModel):
    """Request body for renaming a conversation."""

    title: str = Field(min_length=1, max_length=100)


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


def _check_agent_rate_limit(current_user: AuthenticatedUser) -> None:
    """Apply the agent chat rate limit to both normal and approval requests."""

    rate_limit = check_rate_limit(
        user_id=str(current_user.id),
        action="agent_chat",
        limit=20,
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


class ConversationUnavailableError(Exception):
    """Conversation does not exist or has been deleted."""


def _get_or_create_conversation(
    current_user: AuthenticatedUser,
    conversation_id: str | None,
    first_message: str,
) -> tuple[str, str]:
    """
    Verify conversation ownership if ID is provided, or create a new conversation
    with the user's first message as its conversation title.

    Returns:
        (conversation_id, thread_id)
    """
    if conversation_id:
        try:
            conv_uuid = UUID(conversation_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid conversation ID format.",
            )

        thread_id = f"{current_user.id}:{conversation_id}"

        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id FROM conversations
                    WHERE id = :id AND auth_user_id = :user_id AND NOT is_deleted
                """),
                {"id": str(conv_uuid), "user_id": str(current_user.id)},
            ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied.",
            )

        thread_id = f"{current_user.id}:{conversation_id}"
        return conversation_id, thread_id

    # New conversation creation
    title = first_message.strip() or "New Booking Chat"
    with engine.begin() as conn:
        new_row = conn.execute(
            text("""
                INSERT INTO conversations (auth_user_id, title)
                VALUES (:user_id, :title)
                RETURNING id
            """),
            {"user_id": str(current_user.id), "title": title},
        ).mappings().first()

    if new_row is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to create conversation.",
        )

    new_conv_id = str(new_row["id"])
    thread_id = f"{current_user.id}:{new_conv_id}"
    return new_conv_id, thread_id


def _create_pending_turn(
    conversation_id: str,
    user_message: str,
) -> str:
    """
    Persist the user message immediately as a pending conversation turn with
    assistant_message = NULL. Locks the parent conversation row to serialise
    turn_number allocation under concurrent requests.

    Returns the new turn's UUID so the caller can later complete it via
    _complete_turn() once the agent has responded.
    """
    with engine.begin() as conn:
        # Acquire a row-level lock on the conversation so that two concurrent
        # requests for the same conversation cannot race on MAX(turn_number).
        # Under READ COMMITTED, a concurrent delete that commits first makes this
        # SELECT return no row, so a deleted conversation can never get new turns.
        locked = conn.execute(
            text("""
                SELECT id FROM conversations
                WHERE id = :conv_id AND NOT is_deleted
                FOR UPDATE
            """),
            {"conv_id": conversation_id},
        ).first()
        if locked is None:
            raise ConversationUnavailableError(conversation_id)

        turn_row = conn.execute(
            text("""
                INSERT INTO conversation_turns
                    (conversation_id, turn_number, user_message, assistant_message, metadata)
                VALUES (
                    :conv_id,
                    (SELECT COALESCE(MAX(turn_number), 0) + 1
                     FROM conversation_turns
                     WHERE conversation_id = :conv_id),
                    :user_message,
                    NULL,
                    NULL
                )
                RETURNING id
            """),
            {"conv_id": conversation_id, "user_message": user_message},
        ).mappings().first()

    if turn_row is None:
        raise RuntimeError("Failed to create conversation turn.")

    return str(turn_row["id"])


def _complete_turn(
    turn_id: str,
    conversation_id: str,
    assistant_message: str,
    metadata: dict | None = None,
) -> None:
    """
    Fill in the assistant response for a previously created pending turn and
    touch conversations.updated_at so the sidebar sorts correctly.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE conversation_turns
                SET assistant_message = :assistant_message,
                    metadata          = :metadata
                WHERE id = :turn_id
            """),
            {
                "turn_id": turn_id,
                "assistant_message": assistant_message,
                "metadata": json.dumps(metadata) if metadata else None,
            },
        )
        conn.execute(
            text("UPDATE conversations SET updated_at = NOW() WHERE id = :conv_id"),
            {"conv_id": conversation_id},
        )


# ============================================================
# Agent Chat: Streaming helpers
# ============================================================


def _build_agent_payload(
    result: dict[str, Any],
    conversation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Turn a run_agent() result into the API payload sent to the browser and
    the metadata persisted with the assistant message.
    """

    response_payload: dict[str, Any] = {
        "success": True,
        "conversation_id": conversation_id,
        "response": result["final_response"],
    }

    msg_metadata: dict[str, Any] = {}
    if result.get("__interrupt__"):
        response_payload["approval_required"] = True
        msg_metadata["approval_required"] = True

    booking_ctx = result.get("booking_context", {})
    if booking_ctx.get("booking_id"):
        booking_data = {
            "booking_id": booking_ctx.get("booking_id"),
            "booking_reference": booking_ctx.get("booking_reference"),
            "status": booking_ctx.get("booking_status"),
            "total_amount": booking_ctx.get("total_amount"),
        }
        response_payload["booking"] = booking_data
        msg_metadata["booking"] = booking_data

    boarding_stop_id = booking_ctx.get("boarding_stop_id")
    dropping_stop_id = booking_ctx.get("dropping_stop_id")
    current_segment = (
        f"{boarding_stop_id}:{dropping_stop_id}"
        if boarding_stop_id and dropping_stop_id
        else None
    )
    stored_segment = booking_ctx.get("seat_map_segment")
    stored_seats = booking_ctx.get("seat_map")
    in_seat_selection = bool(
        not booking_ctx.get("booking_id")
        and current_segment
        and stored_segment == current_segment
        and isinstance(stored_seats, list)
    )

    if in_seat_selection:
        # Lightweight and sent on every response in this phase, so the
        # frontend can highlight the seat the application actually resolved.
        selected_seat_label = (
            str(booking_ctx["seat_number"]) if booking_ctx.get("seat_number") else None
        )
        response_payload["selected_seat"] = selected_seat_label
        msg_metadata["selected_seat"] = selected_seat_label

    # The map itself is attached only to the response of the turn in which
    # availability was checked (after boarding and dropping are known).
    if in_seat_selection and booking_ctx.get("seat_map_fresh"):
        map_seats = []
        held_seat_number = (
            str(booking_ctx.get("seat_number"))
            if booking_ctx.get("hold_id") and booking_ctx.get("seat_number")
            else None
        )
        for seat in stored_seats:
            if (
                not isinstance(seat, dict)
                or seat.get("seat_number") is None
                or seat.get("seat_type") is None
                or seat.get("status") not in {"available", "unavailable"}
            ):
                raise ValueError("Stored seat map contains an invalid seat record.")
            map_seats.append(
                {
                    "seat_number": str(seat["seat_number"]),
                    "seat_type": str(seat["seat_type"]),
                    "row_number": seat.get("row_number"),
                    "column_number": seat.get("column_number"),
                    "status": (
                        "held_by_you"
                        if held_seat_number
                        and str(seat["seat_number"]) == held_seat_number
                        else seat["status"]
                    ),
                }
            )
        seat_map = {
            "bus_type": (
                booking_ctx.get("bus_type")
                if isinstance(booking_ctx.get("bus_type"), str)
                else None
            ),
            "selected_seat": (
                str(booking_ctx["seat_number"])
                if booking_ctx.get("seat_number")
                else None
            ),
            "seats": map_seats,
        }
        response_payload["seat_map"] = seat_map
        msg_metadata["seat_map"] = seat_map

    if booking_ctx.get("payment_order_id"):
        payment_order_data = {
            "payment_id": booking_ctx.get("payment_id"),
            "order_id": booking_ctx.get("payment_order_id"),
            "amount": booking_ctx.get("payment_order_amount"),
            "currency": booking_ctx.get("payment_currency"),
        }
        response_payload["payment_order"] = payment_order_data
        msg_metadata["payment_order"] = payment_order_data

    return response_payload, msg_metadata


def _stream_agent_turn(
    run_turn: Callable[[], dict[str, Any]],
    finalize_turn: Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]],
) -> StreamingResponse:
    """
    Run one agent turn in a worker thread and stream it as Server-Sent Events.

    Events:
        step  - one agent step (running / done / error), may repeat per step ID
        final - the same payload the old JSON endpoint returned
        error - {"status": int, "detail": str}; always the last event

    The worker thread also persists the turn (finalize_turn), so the
    conversation is saved even if the browser disconnects mid-stream.
    """

    events: queue.Queue = queue.Queue()
    steps_by_id: dict[str, dict[str, Any]] = {}

    def on_step(step: dict[str, Any]) -> None:
        steps_by_id[step["id"]] = step
        events.put(("step", step))

    def worker() -> None:
        token = set_step_emitter(on_step)
        try:
            result = run_turn()
            payload = finalize_turn(result, list(steps_by_id.values()))
            events.put(("final", payload))
        except PermissionError as exc:
            events.put(("error", {"status": 403, "detail": str(exc)}))
        except ValueError as exc:
            events.put(("error", {"status": 400, "detail": str(exc)}))
        except Exception as exc:
            print(f"[CHAT STREAM] Unexpected agent error: {exc!r}")
            events.put((
                "error",
                {
                    "status": 500,
                    "detail": "The agent failed to process your request.",
                },
            ))
        finally:
            reset_step_emitter(token)
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        while True:
            item = events.get()
            if item is None:
                break
            name, data = item
            yield f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# Agent Chat: Normal Message
# ============================================================


@app.post("/api/v1/chat")
def chat_with_agent(
    chat_request: AgentChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Send a normal user message to the bus-booking AI agent.

    Creates the conversation on the first message if conversation_id is omitted,
    persists messages and keeps the first user message as the conversation title.

    Responds with a Server-Sent Events stream of agent steps followed by a
    final event carrying the chat payload.
    """
    _check_agent_rate_limit(current_user)

    user_text = chat_request.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    conversation_id, thread_id = _get_or_create_conversation(
        current_user=current_user,
        conversation_id=chat_request.conversation_id,
        first_message=user_text,
    )

    # Persist the user message immediately (assistant_message = NULL).
    # The turn is completed after the agent responds. If the agent fails,
    # the pending turn (user_message only) remains in the database.
    turn_id: str | None = None
    try:
        turn_id = _create_pending_turn(conversation_id, user_text)
    except ConversationUnavailableError:
        # Deleted between ownership check and turn insert: do not run the agent.
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )
    except Exception as exc:
        print(f"[CHAT PERSISTENCE] Warning creating pending turn: {exc}")

    def run_turn() -> dict[str, Any]:
        return run_agent(
            current_user=current_user,
            user_message=user_text,
            thread_id=thread_id,
        )

    def finalize_turn(
        result: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        response_payload, msg_metadata = _build_agent_payload(
            result,
            conversation_id,
        )

        if steps:
            msg_metadata["steps"] = steps

        # Complete the pending turn with the assistant response.
        if turn_id is not None:
            try:
                _complete_turn(
                    turn_id=turn_id,
                    conversation_id=conversation_id,
                    assistant_message=result["final_response"],
                    metadata=msg_metadata or None,
                )
            except Exception as exc:
                print(f"[CHAT PERSISTENCE] Warning completing turn: {exc}")

        return response_payload

    return _stream_agent_turn(run_turn, finalize_turn)


# ============================================================
# Agent Chat: Human Approval
# ============================================================


@app.post("/api/v1/chat/approval")
def approve_agent_action(
    request: Request,
    approval_request: AgentApprovalRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Approve or reject a pending human-in-the-loop agent action.

    Resumes the existing LangGraph thread and persists the approval turn.
    Streams agent steps the same way as /api/v1/chat.
    """
    _check_agent_rate_limit(current_user)

    conversation_id = approval_request.conversation_id or request.cookies.get("bus_booking_conversation_id")
    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="No active conversation thread found to approve. Start a booking flow first.",
        )
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID format.",
        )

    thread_id = f"{current_user.id}:{conversation_id}"

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, is_deleted FROM conversations
                WHERE id = :id AND auth_user_id = :user_id
            """),
            {"id": str(conv_uuid), "user_id": str(current_user.id)},
        ).mappings().first()

    # A deleted conversation must never resume (its LangGraph checkpoint may
    # still exist), so reject it before the legacy-session fallback below.
    if row and row["is_deleted"]:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )

    if not row:
        # If not in conversations table, check if an active thread exists in LangGraph (e.g. tests or legacy session)
        chk = graph.get_state({"configurable": {"thread_id": thread_id, "current_user": current_user}})
        if chk and chk.values:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO conversations (id, auth_user_id, title)
                            VALUES (:id, :user_id, 'Booking Flow')
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {"id": str(conv_uuid), "user_id": str(current_user.id)},
                    )
            except Exception as e:
                print(f"[APPROVAL AUTO-CREATE] {e}")
        else:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied.",
            )

    def run_turn() -> dict[str, Any]:
        return run_agent(
            current_user=current_user,
            user_message=approval_request.approval_decision,
            thread_id=thread_id,
            approval_decision=approval_request.approval_decision,
        )

    def finalize_turn(
        result: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        response_payload, msg_metadata = _build_agent_payload(
            result,
            conversation_id,
        )

        if steps:
            msg_metadata["steps"] = steps

        # Persist the approval decision as a conversation turn.
        approval_turn_id: str | None = None
        try:
            decision_label = (
                "Approved the action"
                if approval_request.approval_decision == "approve"
                else "Rejected the action"
            )
            approval_turn_id = _create_pending_turn(conversation_id, decision_label)
        except Exception as exc:
            print(f"[APPROVAL PERSISTENCE] Warning creating pending turn: {exc}")

        if approval_turn_id is not None:
            try:
                _complete_turn(
                    turn_id=approval_turn_id,
                    conversation_id=conversation_id,
                    assistant_message=result["final_response"],
                    metadata=msg_metadata or None,
                )
            except Exception as exc:
                print(f"[APPROVAL PERSISTENCE] Warning completing turn: {exc}")

        return response_payload

    return _stream_agent_turn(run_turn, finalize_turn)


# ============================================================
# Conversations REST API
# ============================================================


@app.get("/api/v1/conversations")
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    cursor_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List conversations for the authenticated user, newest first, with cursor pagination
    and optional case-insensitive title search.
    """
    params: dict = {
        "user_id": str(current_user.id),
        "fetch_limit": limit + 1,
    }

    where_clauses = ["c.auth_user_id = :user_id", "NOT c.is_deleted"]

    if search and search.strip():
        where_clauses.append(
            "COALESCE(first_turn.user_message, c.title) ILIKE :search_pattern"
        )
        params["search_pattern"] = f"%{search.strip()}%"

    if cursor and cursor_id:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
            cursor_uuid = UUID(cursor_id)
            where_clauses.append("(updated_at, id) < (:cursor_dt, :cursor_uuid)")
            params["cursor_dt"] = cursor_dt
            params["cursor_uuid"] = str(cursor_uuid)
        except Exception:
            pass

    query_str = f"""
        SELECT
            c.id,
            COALESCE(first_turn.user_message, c.title) AS title,
            c.created_at,
            c.updated_at
        FROM conversations AS c
        LEFT JOIN LATERAL (
            SELECT user_message
            FROM conversation_turns
            WHERE conversation_id = c.id AND user_message IS NOT NULL
            ORDER BY turn_number ASC
            LIMIT 1
        ) AS first_turn ON TRUE
        WHERE {' AND '.join(where_clauses)}
        ORDER BY c.updated_at DESC, c.id DESC
        LIMIT :fetch_limit
    """

    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(query_str), params).mappings().fetchall()]

    has_more = len(rows) > limit
    returned_rows = rows[:limit]

    next_cursor = None
    next_cursor_id = None
    if has_more and returned_rows:
        last_item = returned_rows[-1]
        next_cursor = (
            last_item["updated_at"].isoformat()
            if isinstance(last_item["updated_at"], datetime)
            else str(last_item["updated_at"])
        )
        next_cursor_id = str(last_item["id"])

    # Convert timestamps and UUIDs for JSON serialization
    serialized = []
    for r in returned_rows:
        serialized.append({
            "id": str(r["id"]),
            "title": r["title"],
            "created_at": (
                r["created_at"].isoformat()
                if isinstance(r["created_at"], datetime)
                else str(r["created_at"])
            ),
            "updated_at": (
                r["updated_at"].isoformat()
                if isinstance(r["updated_at"], datetime)
                else str(r["updated_at"])
            ),
        })

    return {
        "success": True,
        "conversations": serialized,
        "next_cursor": next_cursor,
        "next_cursor_id": next_cursor_id,
        "has_more": has_more,
    }


@app.get("/api/v1/conversations/{conversation_id}")
def get_conversation_details(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve conversation messages, plus authoritative pending approval (from LangGraph)
    and validated active payment order and confirmed ticket.
    """
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    with engine.connect() as conn:
        conv_row = conn.execute(
            text("""
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = :id AND auth_user_id = :user_id AND NOT is_deleted
            """),
            {"id": str(conv_uuid), "user_id": str(current_user.id)},
        ).mappings().first()

        if not conv_row:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        turn_rows = conn.execute(
            text("""
                SELECT id, turn_number, user_message, assistant_message, metadata, created_at
                FROM conversation_turns
                WHERE conversation_id = :id
                ORDER BY turn_number ASC
            """),
            {"id": str(conv_uuid)},
        ).mappings().fetchall()

    # Expand each turn into two ChatMessage items (user + assistant)
    # preserving the existing frontend messages[] contract (Option A).
    # assistant_message is omitted for pending turns (still NULL).
    messages = []
    for turn in turn_rows:
        ts = (
            turn["created_at"].isoformat()
            if isinstance(turn["created_at"], datetime)
            else str(turn["created_at"])
        )
        # User message (always present)
        messages.append({
            "id": f"{turn['id']}-user",
            "role": "user",
            "content": turn["user_message"],
            "metadata": None,
            "created_at": ts,
        })
        # Assistant message (omit if still pending / agent failed)
        if turn["assistant_message"] is not None:
            meta = turn["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = None
            messages.append({
                "id": f"{turn['id']}-assistant",
                "role": "assistant",
                "content": turn["assistant_message"],
                "metadata": meta,
                "created_at": ts,
            })

    # Read LangGraph state for authoritative interrupts and booking context
    thread_id = f"{current_user.id}:{conversation_id}"
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "current_user": current_user,
        }
    }

    pending_approval = None
    pending_payment_order = None
    confirmed_ticket = None

    try:
        checkpoint = graph.get_state(config)
        if checkpoint and checkpoint.tasks:
            for task in checkpoint.tasks:
                interrupts = getattr(task, "interrupts", ())
                if interrupts:
                    first_int = interrupts[0]
                    val = getattr(first_int, "value", {})
                    msg = val.get("message") if isinstance(val, dict) else str(val)
                    pending_approval = {
                        "prompt": msg or "Please approve or reject this action."
                    }
                    break

        existing_values = checkpoint.values if checkpoint else {}
        booking_ctx = existing_values.get("booking_context", {}) if existing_values else {}

        # Validate pending payment order (hold must be ACTIVE and not expired)
        if booking_ctx.get("payment_order_id") and booking_ctx.get("hold_id"):
            hold_id = booking_ctx.get("hold_id")
            order_id = booking_ctx.get("payment_order_id")

            with engine.connect() as conn:
                hold_row = conn.execute(
                    text("SELECT status, expires_at FROM seat_holds WHERE id = :h_id"),
                    {"h_id": hold_id},
                ).mappings().first()
                pay_row = conn.execute(
                    text("SELECT status FROM payments WHERE provider_order_id = :o_id"),
                    {"o_id": order_id},
                ).mappings().first()

            is_hold_valid = False
            if hold_row and hold_row["status"] == "ACTIVE":
                exp = hold_row["expires_at"]
                if exp:
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp > datetime.now(timezone.utc):
                        is_hold_valid = True

            is_pay_valid = pay_row and pay_row["status"] == "PENDING"

            if is_hold_valid and is_pay_valid:
                pending_payment_order = {
                    "payment_order": {
                        "payment_id": booking_ctx.get("payment_id"),
                        "order_id": booking_ctx.get("payment_order_id"),
                        "amount": booking_ctx.get("payment_order_amount"),
                        "currency": booking_ctx.get("payment_currency"),
                    },
                    "booking": {
                        "booking_id": booking_ctx.get("booking_id"),
                        "booking_reference": booking_ctx.get("booking_reference"),
                        "status": booking_ctx.get("booking_status"),
                        "total_amount": booking_ctx.get("total_amount"),
                    },
                }

        # Check confirmed ticket if booking completed
        booking_id = booking_ctx.get("booking_id")
        if booking_id:
            with engine.connect() as conn:
                b_row = conn.execute(
                    text("SELECT status FROM bookings WHERE id = :b_id"),
                    {"b_id": booking_id},
                ).mappings().first()
            if b_row and b_row["status"] == "CONFIRMED":
                confirmed_ticket = _get_confirmed_ticket_details(UUID(str(booking_id)))

    except Exception as exc:
        print(f"[CONVERSATION RESTORE] Warning reading LangGraph state: {exc}")

    return {
        "success": True,
        "id": str(conv_row["id"]),
        "title": conv_row["title"],
        "created_at": (
            conv_row["created_at"].isoformat()
            if isinstance(conv_row["created_at"], datetime)
            else str(conv_row["created_at"])
        ),
        "updated_at": (
            conv_row["updated_at"].isoformat()
            if isinstance(conv_row["updated_at"], datetime)
            else str(conv_row["updated_at"])
        ),
        "messages": messages,
        "pending_approval": pending_approval,
        "pending_payment_order": pending_payment_order,
        "confirmed_ticket": confirmed_ticket,
    }


@app.patch("/api/v1/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    request_data: RenameConversationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Rename a conversation owned by the authenticated user."""
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    new_title = request_data.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE conversations
                SET title = :title, updated_at = NOW()
                WHERE id = :id AND auth_user_id = :user_id AND NOT is_deleted
            """),
            {"id": str(conv_uuid), "title": new_title, "user_id": str(current_user.id)},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    return {
        "success": True,
        "id": conversation_id,
        "title": new_title,
    }


@app.delete("/api/v1/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Soft-delete a conversation (is_deleted = TRUE) so it disappears from the
    sidebar and every read/write endpoint, then clear its LangGraph checkpoints.
    """
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    thread_id = f"{current_user.id}:{conversation_id}"

    # Soft-delete the database record FIRST, scoped to the owner and to rows
    # that are still live (a repeat delete matches nothing -> 404).
    # Checkpoint cleanup happens AFTER this commits, so a database failure
    # cannot destroy checkpoint state prematurely.
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE conversations
                SET is_deleted = TRUE
                WHERE id = :id AND auth_user_id = :user_id AND NOT is_deleted
            """),
            {"id": str(conv_uuid), "user_id": str(current_user.id)},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    # Best-effort: the conversation is already hidden, so a cleanup failure
    # must not turn a successful delete into an error for the user.
    try:
        delete_thread = getattr(checkpointer, "delete_thread", None)
        if callable(delete_thread):
            delete_thread(thread_id)
    except Exception as exc:
        print(f"[CONVERSATION DELETE] Checkpoint cleanup failed for {thread_id}: {exc}")

    return {
        "success": True,
        "id": conversation_id,
    }


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