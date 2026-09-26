from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    run_agent,
)

from bus_booking_ai_agent.phase_05_memory.memory_service import (
    save_memory,
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


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Bus Booking AI Agent",
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


@app.post("/api/v1/dev/payments/verify")
async def verify_payment_endpoint(
    request: VerifyPaymentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Verify a Razorpay payment signature.

    Successful verification changes the payment state
    from CREATED to SUCCESS.

    Booking confirmation is handled separately.
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

        return {
            "success": True,
            **result,
        }

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

    except PaymentError as error:
        return {
            "success": False,
            "error": str(error),
        }

# ============================================================
# Agent Chat
# ============================================================


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)


class UpdateMemoryRequest(BaseModel):
    memory_type: str = Field(min_length=1)
    memory_key: str = Field(min_length=1)
    memory_value: str = Field(min_length=1)


@app.post("/api/v1/chat")
def chat_with_agent(
    request: AgentChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Run the bus-booking agent for the authenticated user.

    The client supplies a conversation identifier, but never supplies
    the authenticated user's UUID. The server namespaces the LangGraph
    thread with the authenticated Supabase user ID.
    """
    thread_id = f"{current_user.id}:{request.conversation_id}"

    result = run_agent(
        current_user=current_user,
        user_message=request.message,
        thread_id=thread_id,
    )

    return {
        "success": True,
        "conversation_id": request.conversation_id,
        "response": result["final_response"],
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

