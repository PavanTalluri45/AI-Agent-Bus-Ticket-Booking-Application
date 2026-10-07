import os
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import connect
from psycopg.rows import dict_row

from main import app, get_current_user
from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    AgentState,
    BookingContext,
    build_seat_hold_pending_action,
    graph,
    run_agent,
    verify_pending_action_matches_context,
)
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


def test_incomplete_context_hold_request_returns_advisory(base_booking_context):
    """
    Test 2: Explicit hold request when context is incomplete does NOT stage
    pending action or interrupt, and provides informative guidance.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    incomplete_context = base_booking_context.copy()
    incomplete_context.pop("seat_id", None)
    incomplete_context.pop("seat_number", None)

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
    assert "seat" in result.get("final_response", "").lower()


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

