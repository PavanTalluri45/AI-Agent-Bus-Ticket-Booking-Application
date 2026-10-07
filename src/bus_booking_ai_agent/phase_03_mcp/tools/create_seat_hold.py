"""
Application-level Gemini action tool for requesting a temporary seat hold.

Important architecture:
    Gemini
        ↓
    create_seat_hold()
        ↓
    application validation
        ↓
    HITL approval
        ↓
    hold_execution_node()
        ↓
    create_hold()
        ↓
    PostgreSQL

This module intentionally does NOT:
- call the MCP server
- accept UUIDs from Gemini
- access PostgreSQL directly
- create the database hold
- receive the authenticated user from the model

The actual database mutation remains in hold_service.create_hold()
and is executed by the authenticated application workflow after HITL approval.
"""

from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict


# ============================================================================
# Tool Name
# ============================================================================

CREATE_SEAT_HOLD_TOOL_NAME = "create_seat_hold"


# ============================================================================
# Booking Context Contract
# ============================================================================


class _SeatHoldRequiredContext(TypedDict):
    """Identifiers that must exist before a hold can be requested."""

    schedule_id: str
    seat_id: str
    boarding_stop_id: str
    dropping_stop_id: str


class SeatHoldBookingContext(_SeatHoldRequiredContext, total=False):
    """
    Minimum application state required to request a seat hold.

    These values must already have been resolved by the application from
    authoritative MCP/database results.

    The four identifiers above are required. Everything below is optional.
    """

    seat_number: str
    boarding_stop_name: str
    dropping_stop_name: str

    bus_number: str
    operator_name: str
    bus_type: str

    origin: str
    destination: str
    travel_date: str

    hold_id: str
    hold_expires_at: str


# ============================================================================
# Gemini Tool Input
# ============================================================================


class CreateSeatHoldArguments(BaseModel):
    """
    Gemini input schema for the create_seat_hold action.

    The model supplies no identifiers. The application obtains every
    identifier from authoritative booking context.
    """

    model_config = ConfigDict(
        extra="forbid",
    )


# ============================================================================
# Gemini Tool Definition
# ============================================================================


CREATE_SEAT_HOLD_TOOL: dict[str, Any] = {
    "type": "function",
    "name": CREATE_SEAT_HOLD_TOOL_NAME,
    "description": (
        "Request a temporary 10-minute hold for the currently selected seat. "
        "Use this tool only when the user explicitly asks to hold or reserve "
        "the selected seat temporarily. Do not use it merely because a seat "
        "was selected. The application will request explicit confirmation "
        "before creating the hold."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


# ============================================================================
# Tool Input Validation
# ============================================================================


class SeatHoldToolError(ValueError):
    """Raised when the seat-hold action cannot be requested safely."""


def validate_create_seat_hold_arguments(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate Gemini's arguments.

    The expected input is an empty JSON object.

    Example:
        {}

    Any model-supplied field is rejected.
    """

    if not isinstance(arguments, dict):
        raise SeatHoldToolError(
            "create_seat_hold arguments must be an object."
        )

    try:
        validated = CreateSeatHoldArguments.model_validate(arguments)
    except Exception as error:
        raise SeatHoldToolError(
            f"Invalid arguments for '{CREATE_SEAT_HOLD_TOOL_NAME}': {error}"
        ) from error

    return validated.model_dump(mode="json")


# ============================================================================
# Booking Context Validation
# ============================================================================


_REQUIRED_CONTEXT_FIELDS = (
    "schedule_id",
    "seat_id",
    "boarding_stop_id",
    "dropping_stop_id",
)


def validate_seat_hold_context(
    context: SeatHoldBookingContext,
) -> None:
    """
    Verify that the application has resolved everything required for a hold.

    The identifiers must come from authoritative application state.
    Gemini is never allowed to provide or invent them.

    The TypedDict only describes the shape for the type checker. This check
    is what actually catches missing or empty values at runtime.
    """

    missing_fields = [
        field
        for field in _REQUIRED_CONTEXT_FIELDS
        if not context.get(field)
    ]

    if missing_fields:
        raise SeatHoldToolError(
            "Cannot create a seat-hold request because the booking context "
            f"is missing: {', '.join(missing_fields)}. "
            "Select a bus, journey segment, and available seat first."
        )

    if context.get("hold_id"):
        raise SeatHoldToolError(
            "An active seat hold already exists for the selected seat."
        )


# ============================================================================
# Pending Action Contract
# ============================================================================


class PendingSeatHoldAction(TypedDict):
    """Action payload stored by the LangGraph HITL workflow."""

    action: str
    arguments: dict[str, Any]


# ============================================================================
# Pending Action Builder
# ============================================================================


def build_seat_hold_pending_action(
    context: SeatHoldBookingContext,
) -> PendingSeatHoldAction:
    """
    Build the pending HITL action from authoritative application state.

    No identifier is taken from Gemini.
    """

    validate_seat_hold_context(context)

    return {
        "action": CREATE_SEAT_HOLD_TOOL_NAME,
        "arguments": {
            "schedule_id": str(context.get("schedule_id") or ""),
            "seat_id": str(context.get("seat_id") or ""),
            "boarding_stop_id": str(context.get("boarding_stop_id") or ""),
            "dropping_stop_id": str(context.get("dropping_stop_id") or ""),
            "seat_number": str(context.get("seat_number") or ""),
            "boarding_stop_name": str(context.get("boarding_stop_name") or ""),
            "dropping_stop_name": str(context.get("dropping_stop_name") or ""),
            "bus_number": str(context.get("bus_number") or ""),
            "operator_name": str(context.get("operator_name") or ""),
            "bus_type": str(context.get("bus_type") or ""),
            "origin": str(context.get("origin") or ""),
            "destination": str(context.get("destination") or ""),
            "travel_date": str(context.get("travel_date") or ""),
        },
    }


# ============================================================================
# Explicit Intent Helper
# ============================================================================


def user_explicitly_requested_hold(user_message: str) -> bool:
    """
    Detect explicit temporary-hold intent at the application boundary.

    This is deliberately conservative.

    Seat selection alone must not trigger a hold.
    """

    normalized = " ".join(
        user_message.lower().strip().split()
    )

    explicit_phrases = (
        "hold this seat",
        "hold the seat",
        "hold seat",
        "place a hold",
        "place hold",
        "temporary hold",
        "reserve this seat temporarily",
        "reserve the seat temporarily",
        "temporarily reserve",
    )

    return any(
        phrase in normalized
        for phrase in explicit_phrases
    )


# ============================================================================
# Public Exports
# ============================================================================


__all__ = [
    "CREATE_SEAT_HOLD_TOOL_NAME",
    "CREATE_SEAT_HOLD_TOOL",
    "CreateSeatHoldArguments",
    "SeatHoldToolError",
    "SeatHoldBookingContext",
    "PendingSeatHoldAction",
    "validate_create_seat_hold_arguments",
    "validate_seat_hold_context",
    "build_seat_hold_pending_action",
    "user_explicitly_requested_hold",
]