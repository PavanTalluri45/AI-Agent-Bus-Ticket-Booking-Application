from uuid import UUID

from fastapi import Depends, FastAPI

from bus_booking_ai_agent.auth import (
    AuthenticatedUser,
    get_current_user,
)

from bus_booking_ai_agent.services.hold_models import (
    CreateHoldRequest,
)

from bus_booking_ai_agent.services.hold_service import (
    create_hold,
    HoldConflictError,
    InvalidJourneySegmentError,
    ScheduleNotFoundError,
    ScheduleUnavailableError,
    SeatNotAvailableError,
)

app = FastAPI(
    title="Bus Booking AI Agent",
)


@app.get("/")
async def read_root():
    return {
        "status": "ok",
        "service": "bus-booking-ai-agent",
    }


@app.get(
    "/api/v1/auth/me",
    response_model=AuthenticatedUser,
)
async def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> AuthenticatedUser:
    """
    Return the currently authenticated user.

    The identity comes from Supabase Auth through
    the verified access token.
    """

    return current_user


@app.post("/api/v1/dev/holds")
async def create_development_hold(
    request: CreateHoldRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
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