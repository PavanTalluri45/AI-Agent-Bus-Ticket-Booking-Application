
"""
Application-level action for creating a payment-pending booking.

This module does not:
- Connect to MCP or PostgreSQL directly.
- Accept internal identifiers from Gemini.
- Create bookings before HITL approval.

The authenticated LangGraph workflow executes the real booking service
only after the pending action has been approved.
"""

from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CREATE_BOOKING_ACTION = "create_payment_pending_booking"


class BookingContextForCreation(TypedDict, total=False):
    """Authoritative application context from the existing agent."""

    hold_id: str
    hold_expires_at: str
    seat_number: str
    bus_number: str
    operator_name: str
    origin: str
    destination: str
    travel_date: str
    boarding_stop_name: str
    dropping_stop_name: str
    booking_id: str
    booking_reference: str
    booking_status: str
    total_amount: str


class CreateBookingArguments(BaseModel):
    """Passenger details supplied by the conversation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    passenger_name: str = Field(min_length=1, max_length=100)
    passenger_age: int = Field(ge=1, le=120)
    passenger_gender: str = Field(min_length=1, max_length=20)

    @field_validator("passenger_gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized in {"MALE", "FEMALE", "OTHER"}:
            return normalized
        if normalized in {"M", "BOY", "MAN"}:
            return "MALE"
        if normalized in {"F", "GIRL", "WOMAN"}:
            return "FEMALE"
        raise ValueError("passenger_gender must be MALE, FEMALE, or OTHER.")


CREATE_BOOKING_TOOL: dict[str, Any] = {
    "type": "function",
    "name": CREATE_BOOKING_ACTION,
    "description": (
        "Request creation of a payment-pending booking for the "
        "currently held seat. Use only when the user wants to proceed "
        "with booking and the passenger's name, age, and gender have "
        "been provided. Never provide internal IDs. The application "
        "will validate the active hold and request approval."
    ),
    "parameters": CreateBookingArguments.model_json_schema(),
}


class BookingActionError(ValueError):
    """Raised when a booking action cannot safely be staged."""


class PendingBookingAction(TypedDict):
    action: str
    arguments: dict[str, Any]


def validate_booking_arguments(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Validate passenger details generated from the conversation."""

    try:
        validated = CreateBookingArguments.model_validate(arguments)
    except ValidationError as exc:
        raise BookingActionError(
            "Passenger details are incomplete or invalid."
        ) from exc

    return validated.model_dump(mode="json")


def build_pending_booking_action(
    context: BookingContextForCreation,
    passenger_arguments: dict[str, Any],
) -> PendingBookingAction:
    """
    Build an action using the existing application hold.

    The model never supplies the hold ID. It is taken from trusted state.
    """
    hold_id = context.get("hold_id")

    if not hold_id:
        raise BookingActionError(
            "An active seat hold is required before booking."
        )

    if context.get("booking_id"):
        raise BookingActionError(
            "A booking has already been created for this conversation."
        )

    passenger = validate_booking_arguments(passenger_arguments)

    return {
        "action": CREATE_BOOKING_ACTION,
        "arguments": {
            "hold_id": hold_id,
            "seat_number": str(context.get("seat_number") or ""),
            "operator_name": str(context.get("operator_name") or ""),
            "bus_type": str(context.get("bus_type") or ""),
            "origin": str(context.get("origin") or ""),
            "destination": str(context.get("destination") or ""),
            "travel_date": str(context.get("travel_date") or ""),
            "boarding_stop_name": str(context.get("boarding_stop_name") or ""),
            "dropping_stop_name": str(context.get("dropping_stop_name") or ""),
            **passenger,
        },
    }
