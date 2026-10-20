import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import connect
from psycopg.rows import dict_row
from sqlalchemy import text

from main import app, get_current_user
from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.database import engine
from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    AgentState,
    BookingContext,
    build_seat_hold_pending_action,
    ensure_selected_schedule_details,
    format_stop_selection_prompt,
    graph,
    llm_node,
    resolve_booking_context,
    run_agent,
    update_booking_context_from_tool_result,
    verify_pending_action_matches_context,
)
import bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent as integrated_agent
from bus_booking_ai_agent.services.hold_service import release_hold


TEST_USER_ID = UUID("7803ebf4-7421-495d-b186-ec01c7c591c3")
TEST_USER = AuthenticatedUser(
    id=TEST_USER_ID,
    email="talluripavankumar88@gmail.com",
    role="authenticated",
    app_metadata={},
    user_metadata={},
)

OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER = AuthenticatedUser(
    id=OTHER_USER_ID,
    email="otheruser@example.com",
    role="authenticated",
    app_metadata={},
    user_metadata={},
)

# Known test fixtures from PostgreSQL
SCHEDULE_ID = "a5ed21c5-94ed-55d3-bec3-d690b67bdd75"
BOARDING_STOP_ID = "1fcffcc3-57bb-5ba1-8009-8a00bc93352d"
DROPPING_STOP_ID = "7fe0f447-e3b2-572d-9e04-2dc47ee2c331"
SEAT_ID = "e99d665c-26ba-576e-9b5f-77e07522a4e4"  # Seat 1B
SEAT_NUMBER = "1B"
ALT_SEAT_ID = "01ff6a9a-07b3-55d5-9454-edea812d01d7"  # Seat 1A
ALT_SEAT_NUMBER = "1A"


def _clean_db():
    try:
        conn_info = (
            f"host={os.getenv('host')} "
            f"port={os.getenv('port')} "
            f"dbname={os.getenv('dbname')} "
            f"user={os.getenv('user')} "
            f"password={os.getenv('password')}"
        )
        with connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE seat_holds SET status = 'RELEASED', released_at = CURRENT_TIMESTAMP WHERE auth_user_id = %s AND status = 'ACTIVE';",
                    (TEST_USER_ID,),
                )
            conn.commit()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")


def _active_hold_count() -> int:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT COUNT(*) FROM seat_holds "
                "WHERE auth_user_id = :user_id AND status = 'ACTIVE'"
            ),
            {"user_id": TEST_USER_ID},
        )
        return int(result.scalar_one())


@pytest.fixture(autouse=True)
def cleanup_holds():
    """Ensure any holds created during tests are released from DB before and after."""
    _clean_db()
    yield
    _clean_db()


@pytest.fixture
def base_booking_context() -> BookingContext:
    """A fully populated booking context up to available seats."""
    return {
        "origin": "Bangalore",
        "destination": "Chennai",
        "travel_date": "2026-09-20",
        "schedule_id": SCHEDULE_ID,
        "operator_name": "SRS Travels",
        "bus_type": "AC Semi-Sleeper",
        "bus_number": "TN02UE1111",
        "boarding_stop_id": BOARDING_STOP_ID,
        "boarding_stop_name": "Bangalore",
        "dropping_stop_id": DROPPING_STOP_ID,
        "dropping_stop_name": "Chennai",
        "available_seats": [
            {"seat_id": SEAT_ID, "seat_number": "1B", "seat_type": "SEATER"},
            {"seat_id": ALT_SEAT_ID, "seat_number": "1A", "seat_type": "SEATER"},
        ],
    }


def test_seat_selection_does_not_hold_or_interrupt(base_booking_context):
    """
    Test 1: Selecting a seat deterministically resolves seat_id & seat_number,
    returns conversational response, does NOT stage pending action, does NOT interrupt,
    and makes zero database writes.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"

    # Setup thread checkpoint with base context
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Search buses",
        "memories": [],
        "booking_context": base_booking_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    # User selects seat 1B
    result = run_agent(
        current_user=TEST_USER,
        user_message="I want seat 1B",
        thread_id=thread_id,
    )

    # Verify context resolution
    context = result.get("booking_context", {})
    assert context.get("seat_number") == "1B"
    assert context.get("seat_id") == SEAT_ID

    # Verify NO hold was created
    assert context.get("hold_id") is None
    assert context.get("hold_expires_at") is None

    # Verify NO interrupt occurred
    assert "__interrupt__" not in result
    assert result.get("approval_status") in {"none", None}
    assert result.get("pending_action") is None

    # Verify conversational response was returned
    assert result.get("final_response") != ""


def test_punctuated_seat_selection_persists_and_followup_stages_hold(
    base_booking_context,
    monkeypatch,
):
    """Resolve seat 1A from availability, checkpoint it, then reuse it on a later hold request."""
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Search buses",
        "memories": [],
        "booking_context": base_booking_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    def fake_interaction(state):
        if state["user_message"] == "I want seat 1A.":
            return SimpleNamespace(
                id="selection-interaction",
                steps=[
                    SimpleNamespace(
                        type="function_call",
                        name="create_seat_hold",
                        arguments={},
                        id="unexpected-hold-call",
                    )
                ],
            )

        assert state["user_message"] == "Okay Go ahead"
        assert state["booking_context"]["seat_id"] == ALT_SEAT_ID
        assert state["booking_context"]["seat_number"] == ALT_SEAT_NUMBER
        return SimpleNamespace(
            id="hold-interaction",
            steps=[
                SimpleNamespace(
                    type="function_call",
                    name="create_seat_hold",
                    arguments={},
                    id="hold-call",
                )
            ],
        )

    monkeypatch.setattr(
        integrated_agent,
        "create_gemini_interaction",
        fake_interaction,
    )

    selected_result = run_agent(
        current_user=TEST_USER,
        user_message="I want seat 1A.",
        thread_id=thread_id,
    )

    assert selected_result.get("__interrupt__") is None
    assert selected_result["booking_context"]["seat_id"] == ALT_SEAT_ID
    assert selected_result["booking_context"]["seat_number"] == ALT_SEAT_NUMBER
    assert selected_result.get("pending_action") is None
    assert "no temporary hold was created" in selected_result["final_response"].lower()
    assert _active_hold_count() == 0

    checkpoint_state = graph.get_state(config).values
    assert checkpoint_state["booking_context"]["seat_id"] == ALT_SEAT_ID
    assert checkpoint_state["booking_context"]["seat_number"] == ALT_SEAT_NUMBER

    hold_result = run_agent(
        current_user=TEST_USER,
        user_message="Okay Go ahead",
        thread_id=thread_id,
    )

    assert "__interrupt__" in hold_result
    assert hold_result["__interrupt__"][0].value["action"] == "create_seat_hold"
    staged_state = graph.get_state(config).values
    assert staged_state["approval_status"] == "pending"
    staged_arguments = staged_state["pending_action"]["arguments"]
    assert staged_arguments["schedule_id"] == SCHEDULE_ID
    assert staged_arguments["seat_id"] == ALT_SEAT_ID
    assert staged_arguments["boarding_stop_id"] == BOARDING_STOP_ID
    assert staged_arguments["dropping_stop_id"] == DROPPING_STOP_ID
    assert staged_state["booking_context"]["seat_number"] == ALT_SEAT_NUMBER
    assert _active_hold_count() == 0


@pytest.mark.parametrize(
    "selection_message",
    ["I want seat 1C.", "I want seat 1A instead of 1B."],
)
def test_unresolved_explicit_seat_selection_is_not_saved(
    base_booking_context,
    monkeypatch,
    selection_message,
):
    """Unavailable or ambiguous requests must not retain a stale seat selection."""
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    context = base_booking_context.copy()
    context["seat_id"] = SEAT_ID
    context["seat_number"] = SEAT_NUMBER
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Search buses",
        "memories": [],
        "booking_context": context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)
    monkeypatch.setattr(
        integrated_agent,
        "create_gemini_interaction",
        lambda state: pytest.fail("Gemini must not claim an unresolved seat was selected"),
    )

    result = run_agent(
        current_user=TEST_USER,
        user_message=selection_message,
        thread_id=thread_id,
    )

    assert "couldn't resolve that seat" in result["final_response"].lower()
    assert "not saved" in result["final_response"].lower()
    assert result["booking_context"].get("seat_id") is None
    assert result["booking_context"].get("seat_number") is None
    assert "__interrupt__" not in result
    assert _active_hold_count() == 0


def test_availability_persistence_updates_authoritative_journey_context(base_booking_context):
    """Seat availability must persist the selected journey IDs and clear stale seat picks."""
    availability_result = {
        "result": [
            {"seat_id": SEAT_ID, "seat_number": SEAT_NUMBER, "seat_type": "SEATER"},
            {"seat_id": ALT_SEAT_ID, "seat_number": ALT_SEAT_NUMBER, "seat_type": "SEATER"},
        ]
    }
    context = base_booking_context.copy()
    context["seat_id"] = ALT_SEAT_ID
    context["seat_number"] = ALT_SEAT_NUMBER

    updated = update_booking_context_from_tool_result(
        context=context,
        tool_name="check_seat_availability",
        tool_result=availability_result,
        tool_arguments={
            "schedule_id": SCHEDULE_ID,
            "boarding_stop_id": BOARDING_STOP_ID,
            "dropping_stop_id": DROPPING_STOP_ID,
        },
    )

    assert updated["schedule_id"] == SCHEDULE_ID
    assert updated["boarding_stop_id"] == BOARDING_STOP_ID
    assert updated["dropping_stop_id"] == DROPPING_STOP_ID
    assert updated["available_seats"] == availability_result["result"]
    assert updated.get("seat_id") is None
    assert updated.get("seat_number") is None


def test_selected_schedule_details_load_stop_options(monkeypatch):
    """A newly selected schedule is hydrated with its authoritative route stops."""
    schedule_context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "available_schedules": [{"schedule_id": SCHEDULE_ID}],
    }

    async def fake_call_mcp_tool(tool_name, arguments):
        assert tool_name == "get_bus_details"
        assert arguments == {"schedule_id": SCHEDULE_ID}
        return {
            "result": {
                "schedule_id": SCHEDULE_ID,
                "boarding_stops": [
                    {"stop_id": BOARDING_STOP_ID, "stop_name": "Hyderabad"},
                ],
                "dropping_stops": [
                    {"stop_id": DROPPING_STOP_ID, "stop_name": "Bangalore"},
                ],
            }
        }

    monkeypatch.setattr(integrated_agent, "call_mcp_tool", fake_call_mcp_tool)

    hydrated = ensure_selected_schedule_details(schedule_context)

    assert hydrated["boarding_stops"] == [
        {"stop_id": BOARDING_STOP_ID, "stop_name": "Hyderabad"},
    ]
    assert hydrated["dropping_stops"] == [
        {"stop_id": DROPPING_STOP_ID, "stop_name": "Bangalore"},
    ]
    assert "Boarding stops: Hyderabad" in format_stop_selection_prompt(hydrated)
    assert "Drop-off stops: Bangalore" in format_stop_selection_prompt(hydrated)


def test_switching_schedules_clears_previous_route_choices():
    """Stops and seats from one schedule must not leak into another selection."""
    context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "boarding_stop_id": BOARDING_STOP_ID,
        "boarding_stops": [
            {"stop_id": BOARDING_STOP_ID, "stop_name": "Old boarding point"},
        ],
        "dropping_stop_id": DROPPING_STOP_ID,
        "dropping_stops": [
            {"stop_id": DROPPING_STOP_ID, "stop_name": "Old drop-off point"},
        ],
        "available_seats": [{"seat_id": SEAT_ID, "seat_number": SEAT_NUMBER}],
        "seat_id": SEAT_ID,
        "seat_number": SEAT_NUMBER,
        "available_schedules": [
            {"schedule_id": SCHEDULE_ID, "operator_name": "Kaveri Travels"},
            {
                "schedule_id": "00000000-0000-0000-0000-000000000002",
                "operator_name": "Morning Star Travels",
            },
        ],
    }

    resolved = resolve_booking_context(context, "I want option 2")

    assert resolved["schedule_id"] == "00000000-0000-0000-0000-000000000002"
    assert "boarding_stops" not in resolved
    assert "dropping_stops" not in resolved
    assert "boarding_stop_id" not in resolved
    assert "dropping_stop_id" not in resolved
    assert "available_seats" not in resolved
    assert "seat_id" not in resolved


def test_availability_request_without_stop_selection_asks_user(monkeypatch):
    """Missing segment choices should not become a guardrail error or MCP call."""
    async def fake_call_mcp_tool(tool_name, arguments):
        assert tool_name == "get_bus_details"
        return {
            "result": {
                "schedule_id": SCHEDULE_ID,
                "boarding_stops": [
                    {"stop_id": BOARDING_STOP_ID, "stop_name": "Hyderabad"},
                ],
                "dropping_stops": [
                    {"stop_id": DROPPING_STOP_ID, "stop_name": "Bangalore"},
                ],
            }
        }

    response = SimpleNamespace(
        id="interaction-id",
        steps=[
            SimpleNamespace(
                type="function_call",
                name="check_seat_availability",
                arguments={},
                id="call-id",
            )
        ],
    )
    monkeypatch.setattr(integrated_agent, "call_mcp_tool", fake_call_mcp_tool)
    monkeypatch.setattr(
        integrated_agent,
        "create_gemini_interaction",
        lambda state: response,
    )

    state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Show me available seats",
        "memories": [],
        "booking_context": {
            "schedule_id": SCHEDULE_ID,
            "available_schedules": [{"schedule_id": SCHEDULE_ID}],
        },
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }

    result = llm_node(state, {})

    assert not result["error"]
    assert not result["tool_name"]
    assert "Boarding stops: Hyderabad" in result["final_response"]
    assert "Drop-off stops: Bangalore" in result["final_response"]
    assert result["booking_context"]["boarding_stops"]


# ============================================================================
# Stop Resolution: Natural Language Input Variants
# ============================================================================


# Shared fixture for stop resolution tests (no DB needed)
STOP_CONTEXT_WITH_LISTS: BookingContext = {
    "schedule_id": SCHEDULE_ID,
    "available_schedules": [{"schedule_id": SCHEDULE_ID}],
    "boarding_stops": [
        {"stop_id": BOARDING_STOP_ID, "stop_name": "Bangalore"},
    ],
    "dropping_stops": [
        {"stop_id": DROPPING_STOP_ID, "stop_name": "Chennai"},
    ],
}


def _make_resolved(msg: str) -> BookingContext:
    """Run resolve_booking_context against STOP_CONTEXT_WITH_LISTS and return result."""
    return resolve_booking_context(STOP_CONTEXT_WITH_LISTS, msg)


# ---- Original format still works ------------------------------------------

def test_stop_resolution_original_format():
    """Original 'Board from X and drop at Y' format continues to work."""
    resolved = _make_resolved("Board from Bangalore and drop at Chennai.")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID, "boarding stop not resolved"
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID, "dropping stop not resolved"
    assert resolved.get("boarding_stop_name") == "Bangalore"
    assert resolved.get("dropping_stop_name") == "Chennai"


# ---- New formats that previously failed -----------------------------------

def test_stop_resolution_boarding_stop_keyword():
    """'Boarding stop X and dropping stop Y' is resolved correctly."""
    resolved = _make_resolved("Boarding stop Bangalore and dropping stop Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_is_phrasing():
    """'My boarding stop is X and dropping stop is Y' is resolved correctly."""
    resolved = _make_resolved("My boarding stop is Bangalore and dropping stop is Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_board_at_get_down():
    """'I want to board at X and get down at Y' is resolved correctly."""
    resolved = _make_resolved("I want to board at Bangalore and get down at Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_from_to_explicit():
    """'From X to Y' with explicit keyword is resolved correctly."""
    resolved = _make_resolved("From Bangalore to Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_city_to_city_bare():
    """'Bangalore to Chennai' (bare, no keyword) uses positional fallback."""
    resolved = _make_resolved("Bangalore to Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_colon_format():
    """'Boarding: X, Dropping: Y' colon-separated format is resolved correctly."""
    resolved = _make_resolved("Boarding: Bangalore, Dropping: Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


# ---- Partial input: only one stop provided --------------------------------

def test_stop_resolution_only_boarding_provided():
    """When only the boarding stop is mentioned, only boarding is resolved."""
    resolved = _make_resolved("Boarding stop Bangalore")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID, "boarding stop must be set"
    # dropping stop must NOT be guessed
    assert resolved.get("dropping_stop_id") is None, "dropping stop must not be invented"


# ---- Ambiguous / unrelated input -----------------------------------------

def test_stop_resolution_ambiguous_message_does_not_resolve():
    """A generic message with no stop names must not resolve either stop."""
    context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "boarding_stops": [
            {"stop_id": BOARDING_STOP_ID, "stop_name": "Bangalore"},
        ],
        "dropping_stops": [
            {"stop_id": DROPPING_STOP_ID, "stop_name": "Chennai"},
        ],
    }
    resolved = resolve_booking_context(context, "What seats are available?")
    assert resolved.get("boarding_stop_id") is None
    assert resolved.get("dropping_stop_id") is None


def test_stop_resolution_case_insensitive():
    """Stop names in any capitalisation are matched correctly."""
    resolved = _make_resolved("boarding stop bangalore and dropping stop chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_does_not_guess_when_ambiguous_stops():
    """When multiple distinct stops match or user mentions two stops, neither is resolved."""
    context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "boarding_stops": [
            {"stop_id": BOARDING_STOP_ID, "stop_name": "Bangalore East"},
            {"stop_id": "00000000-0000-0000-0000-000000000099", "stop_name": "Bangalore West"},
        ],
        "dropping_stops": [
            {"stop_id": DROPPING_STOP_ID, "stop_name": "Chennai"},
        ],
    }
    # Neither East nor West is specified by the user
    resolved = resolve_booking_context(context, "From Bangalore to Chennai")
    assert resolved.get("boarding_stop_id") is None, "unmatched/ambiguous boarding stop must not be resolved"
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID

    # Both East and West mentioned by the user -> ambiguous
    resolved_both = resolve_booking_context(context, "Board from Bangalore East or Bangalore West and drop at Chennai")
    assert resolved_both.get("boarding_stop_id") is None, "multiple mentioned boarding stops must not be resolved"
    assert resolved_both.get("dropping_stop_id") == DROPPING_STOP_ID


def test_stop_resolution_prefers_specific_longer_stop_name():
    """When a stop name contains another (Bangalore City vs Bangalore), user typing the full name resolves cleanly."""
    city_stop_id = "00000000-0000-0000-0000-000000000099"
    context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "boarding_stops": [
            {"stop_id": BOARDING_STOP_ID, "stop_name": "Bangalore"},
            {"stop_id": city_stop_id, "stop_name": "Bangalore City"},
        ],
        "dropping_stops": [
            {"stop_id": DROPPING_STOP_ID, "stop_name": "Chennai"},
        ],
    }
    resolved = resolve_booking_context(context, "From Bangalore City to Chennai")
    assert resolved.get("boarding_stop_id") == city_stop_id
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_partial_stop_selection_prompts_only_for_missing_stop():
    """When one stop is already resolved, format_stop_selection_prompt asks only for the other."""
    from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
        format_stop_selection_prompt,
    )
    context_with_boarding: BookingContext = {
        "boarding_stop_id": BOARDING_STOP_ID,
        "boarding_stop_name": "Bangalore",
        "boarding_stops": [{"stop_id": BOARDING_STOP_ID, "stop_name": "Bangalore"}],
        "dropping_stops": [{"stop_id": DROPPING_STOP_ID, "stop_name": "Chennai"}],
    }
    prompt = format_stop_selection_prompt(context_with_boarding)
    assert "Boarding stop is set to Bangalore" in prompt
    assert "Please choose your dropping stop" in prompt
    assert "Drop-off stops: Chennai" in prompt
    assert "Boarding stops:" not in prompt


def test_stop_resolution_after_clarification_continues_flow():
    """After the agent asks for stops and user responds, both stops are resolved."""
    # Simulate the state after get_bus_details returned stop options and
    # the agent asked the user to choose.  The user now responds.
    resolved = _make_resolved("I want to board at Bangalore and drop off at Chennai")
    assert resolved.get("boarding_stop_id") == BOARDING_STOP_ID
    assert resolved.get("dropping_stop_id") == DROPPING_STOP_ID


def test_format_stop_selection_prompt_no_longer_shows_only_one_format():
    """The stop-selection prompt should no longer funnel users into a single syntax."""
    from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
        format_stop_selection_prompt,
    )
    context: BookingContext = {
        "boarding_stops": [{"stop_name": "Bangalore"}],
        "dropping_stops": [{"stop_name": "Chennai"}],
    }
    prompt = format_stop_selection_prompt(context)
    # The old rigid example "Board from <stop> and drop at <stop>." must be gone
    assert "board from <stop> and drop at <stop>" not in prompt.lower()
    # New prompt should mention multiple examples or "From <stop> to <stop>"
    assert "from" in prompt.lower() and "to" in prompt.lower()


def test_stop_resolution_unrelated_flow_unaffected():
    """Resolving stops must not touch a context that has no stop lists loaded."""
    context: BookingContext = {
        "origin": "Bangalore",
        "destination": "Chennai",
        "travel_date": "2026-09-20",
        "schedule_id": SCHEDULE_ID,
    }
    resolved = resolve_booking_context(context, "Board from Bangalore and drop at Chennai")
    # No stop lists → nothing to resolve
    assert resolved.get("boarding_stop_id") is None
    assert resolved.get("dropping_stop_id") is None
    # Other fields must be untouched
    assert resolved["origin"] == "Bangalore"
    assert resolved["schedule_id"] == SCHEDULE_ID


def test_hold_context_does_not_require_available_seats(base_booking_context):
    """A hold should validate only the authoritative IDs, not the whole available-seats list."""
    hold_context: BookingContext = {
        "schedule_id": SCHEDULE_ID,
        "seat_id": SEAT_ID,
        "seat_number": SEAT_NUMBER,
        "boarding_stop_id": BOARDING_STOP_ID,
        "dropping_stop_id": DROPPING_STOP_ID,
        "origin": "Bangalore",
        "destination": "Chennai",
        "travel_date": "2026-09-20",
        "available_seats": [],
    }

    pending_action = build_seat_hold_pending_action(hold_context)

    assert pending_action["action"] == "create_seat_hold"
    assert pending_action["arguments"]["schedule_id"] == SCHEDULE_ID
    assert pending_action["arguments"]["seat_id"] == SEAT_ID
    assert pending_action["arguments"]["boarding_stop_id"] == BOARDING_STOP_ID
    assert pending_action["arguments"]["dropping_stop_id"] == DROPPING_STOP_ID


def test_incomplete_context_hold_request_returns_advisory(
    base_booking_context,
    monkeypatch,
    capsys,
):
    """
    Test 2: Explicit hold request when context is incomplete does NOT stage
    pending action or interrupt, and provides informative guidance.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    incomplete_context = base_booking_context.copy()
    incomplete_context.pop("seat_id", None)
    incomplete_context.pop("seat_number", None)
    incomplete_context["available_seats"] = []

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Search buses",
        "memories": [],
        "booking_context": incomplete_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    monkeypatch.setattr(
        integrated_agent,
        "create_gemini_interaction",
        lambda state: SimpleNamespace(
            id="missing-seat-interaction",
            steps=[
                SimpleNamespace(
                    type="function_call",
                    name="create_seat_hold",
                    arguments={},
                    id="missing-seat-call",
                )
            ],
        ),
    )

    # User asks to hold seat without choosing one
    result = run_agent(
        current_user=TEST_USER,
        user_message="Please hold this seat",
        thread_id=thread_id,
    )

    # Must NOT interrupt
    assert "__interrupt__" not in result
    assert result.get("approval_status") in {"none", None}
    assert result.get("pending_action") is None
    # Must explain missing selection
    assert "seat_id" in result.get("final_response", "").lower()
    log_output = capsys.readouterr().out
    assert "schedule_id=True" in log_output
    assert "seat_id=False" in log_output
    assert "boarding_stop_id=True" in log_output
    assert "dropping_stop_id=True" in log_output
    assert _active_hold_count() == 0


def test_explicit_hold_intent_triggers_hitl_interrupt(base_booking_context):
    """
    Test 3: When seat is selected, user explicitly asking to hold triggers
    create_seat_hold, stages pending action, and pauses at approval_node interrupt.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "I selected 1B",
        "memories": [],
        "booking_context": ready_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "Seat 1B is selected.",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    # Explicit hold request
    result = run_agent(
        current_user=TEST_USER,
        user_message="Please hold this seat",
        thread_id=thread_id,
    )

    # Verify interrupt triggered
    assert "__interrupt__" in result
    interrupts = result["__interrupt__"]
    assert len(interrupts) > 0
    val = interrupts[0].value
    assert val["type"] == "approval_request"
    assert val["action"] == "create_seat_hold"

    # Verify prompt contents
    prompt = val["message"]
    assert "1B" in prompt
    assert "SRS Travels" in prompt
    assert "10-minute temporary hold" in prompt
    assert "temporary reservation" in prompt

    # Verify checkpoint state
    state = graph.get_state(config).values
    assert state.get("approval_status") == "pending"
    assert state.get("pending_action") is not None
    assert state["pending_action"]["action"] == "create_seat_hold"


def test_approval_resumes_and_creates_real_db_hold(base_booking_context):
    """
    Test 4: Approving the pending action executes create_hold(), creates a real row
    in seat_holds in PostgreSQL, and updates booking context.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "I selected 1B",
        "memories": [],
        "booking_context": ready_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "Seat 1B is selected.",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    # Turn 1: Request hold -> triggers interrupt
    turn1_result = run_agent(
        current_user=TEST_USER,
        user_message="Please hold this seat",
        thread_id=thread_id,
    )
    assert "__interrupt__" in turn1_result
    assert turn1_result.get("approval_status") == "pending"

    # Turn 2: Resume with approval
    result = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )

    # Verify hold creation
    context = result.get("booking_context", {})
    hold_id_str = context.get("hold_id")
    assert hold_id_str is not None
    assert context.get("hold_expires_at") is not None
    assert result.get("approval_status") == "executed"
    assert result.get("pending_action") is None
    assert "successfully held" in result.get("final_response", "").lower()

    # Verify hold exists in PostgreSQL
    conn_info = (
        f"host={os.getenv('host')} "
        f"port={os.getenv('port')} "
        f"dbname={os.getenv('dbname')} "
        f"user={os.getenv('user')} "
        f"password={os.getenv('password')}"
    )
    with connect(conn_info, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, expires_at FROM seat_holds WHERE id = %s;",
                (UUID(hold_id_str),),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["status"] == "ACTIVE"
            assert row["expires_at"] > datetime.now(timezone.utc)

    assert _active_hold_count() == 1


def test_idempotent_approval_replay(base_booking_context):
    """
    Test 5: Resubmitting 'approve' on an active hold returns the existing hold confirmation
    without creating duplicate PostgreSQL rows or throwing an error.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "I selected 1B",
        "memories": [],
        "booking_context": ready_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "Seat 1B is selected.",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    # Turn 1: Hold request
    run_agent(
        current_user=TEST_USER,
        user_message="Please hold this seat",
        thread_id=thread_id,
    )

    # Turn 2: First approval
    result1 = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )
    hold_id_1 = result1["booking_context"]["hold_id"]

    # Turn 3: Replay approval
    result2 = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )
    hold_id_2 = result2["booking_context"]["hold_id"]

    assert hold_id_1 == hold_id_2
    assert result2["approval_status"] == "executed"
    assert "already held" in result2["final_response"].lower()
    assert _active_hold_count() == 1


def test_rejection_clears_pending_action_keeps_seat_zero_db_rows(base_booking_context):
    """
    Test 6: Rejecting a hold request clears pending_action, keeps selected seat
    in context, creates 0 database holds, and returns cancellation message.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    init_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "I selected 1B",
        "memories": [],
        "booking_context": ready_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "Seat 1B is selected.",
        "iteration": 0,
        "error": "",
        "pending_action": None,
        "approval_status": "none",
    }
    graph.update_state(config, init_state)

    # Turn 1: Hold request -> interrupt
    run_agent(
        current_user=TEST_USER,
        user_message="Please hold this seat",
        thread_id=thread_id,
    )

    # Turn 2: Resume with rejection
    result = run_agent(
        current_user=TEST_USER,
        user_message="reject",
        thread_id=thread_id,
        approval_decision="reject",
    )

    # Verify context and state
    context = result.get("booking_context", {})
    assert context.get("seat_number") == "1B"
    assert context.get("seat_id") == SEAT_ID
    assert context.get("hold_id") is None
    assert result.get("approval_status") == "rejected"
    assert result.get("pending_action") is None
    assert "cancelled" in result.get("final_response", "").lower()
    assert _active_hold_count() == 0


def test_context_mismatch_prevents_stale_approval(base_booking_context):
    """
    Test 7: Changing the seat after staging pending action causes verify_pending_action_matches_context
    to fail and raises ValueError on approval attempt.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER
    # Pending action staged for Seat 1B
    pending_action = build_seat_hold_pending_action(ready_context)

    # Context shifted to Seat 1A
    altered_context = ready_context.copy()
    altered_context["seat_id"] = ALT_SEAT_ID
    altered_context["seat_number"] = ALT_SEAT_NUMBER

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    paused_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Please hold this seat",
        "memories": [],
        "booking_context": altered_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 1,
        "error": "",
        "pending_action": pending_action,
        "approval_status": "pending",
    }
    graph.update_state(config, paused_state)

    with pytest.raises(ValueError, match="no longer matches"):
        run_agent(
            current_user=TEST_USER,
            user_message="approve",
            thread_id=thread_id,
            approval_decision="approve",
        )


def test_thread_ownership_security(base_booking_context):
    """
    Test 8: An authenticated user cannot approve another user's conversation thread.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    ready_context = base_booking_context.copy()
    ready_context["seat_id"] = SEAT_ID
    ready_context["seat_number"] = SEAT_NUMBER
    pending_action = build_seat_hold_pending_action(ready_context)

    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}
    paused_state: AgentState = {
        "user_id": str(TEST_USER_ID),
        "user_message": "Please hold this seat",
        "memories": [],
        "booking_context": ready_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 1,
        "error": "",
        "pending_action": pending_action,
        "approval_status": "pending",
    }
    graph.update_state(config, paused_state)

    # Attempting to resume with OTHER_USER must raise PermissionError
    with pytest.raises(PermissionError, match="does not belong"):
        run_agent(
            current_user=OTHER_USER,
            user_message="approve",
            thread_id=thread_id,
            approval_decision="approve",
        )


def test_fastapi_endpoints_separation_and_cookie_guard():
    """
    Test 9: FastAPI endpoints enforce strict separation:
    - /api/v1/chat/approval without cookie returns HTTP 400.
    """
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        client = TestClient(app)

        # Call /api/v1/chat/approval with NO cookie
        resp = client.post("/api/v1/chat/approval", json={"approval_decision": "approve"})
        assert resp.status_code == 400
        assert "No active conversation thread found" in resp.json()["detail"]

    finally:
        app.dependency_overrides.clear()
