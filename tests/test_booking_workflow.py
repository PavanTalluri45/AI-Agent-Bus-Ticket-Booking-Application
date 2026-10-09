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
from bus_booking_ai_agent.phase_03_mcp.tools.create_booking import (
    CREATE_BOOKING_ACTION,
    BookingActionError,
    build_pending_booking_action,
    validate_booking_arguments,
)
from bus_booking_ai_agent.phase_04_langgraph.test_integrated_agent import (
    AgentState,
    BookingContext,
    graph,
    run_agent,
    verify_pending_action_matches_context,
)
from bus_booking_ai_agent.services.hold_service import create_hold
from bus_booking_ai_agent.services.booking_finalization_models import (
    CONFIRM_BOOKING_SQL,
    CONVERT_HOLD_SQL,
    finalize_booking,
)


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
                    """
                    DELETE FROM payments WHERE booking_id IN (
                        SELECT id FROM bookings WHERE auth_user_id = %s
                    );
                    """,
                    (TEST_USER_ID,),
                )
                cur.execute(
                    """
                    DELETE FROM booking_seats WHERE booking_id IN (
                        SELECT id FROM bookings WHERE auth_user_id = %s
                    );
                    """,
                    (TEST_USER_ID,),
                )
                cur.execute(
                    """
                    UPDATE seat_holds 
                    SET status = 'RELEASED', booking_id = NULL, released_at = CURRENT_TIMESTAMP 
                    WHERE auth_user_id = %s;
                    """,
                    (TEST_USER_ID,),
                )
                cur.execute(
                    """
                    DELETE FROM bookings WHERE auth_user_id = %s;
                    """,
                    (TEST_USER_ID,),
                )
                cur.execute(
                    """
                    UPDATE seat_holds SET status = 'RELEASED', released_at = CURRENT_TIMESTAMP
                    WHERE auth_user_id = %s AND status = 'ACTIVE';
                    """,
                    (TEST_USER_ID,),
                )
            conn.commit()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")


@pytest.fixture(autouse=True)
def cleanup_database():
    """Ensure clean state before and after each test."""
    _clean_db()
    yield
    _clean_db()


@pytest.fixture
def base_held_context() -> BookingContext:
    """A context with an active hold created in DB."""
    hold = create_hold(
        current_user=TEST_USER,
        schedule_id=UUID(SCHEDULE_ID),
        seat_id=UUID(SEAT_ID),
        boarding_stop_id=UUID(BOARDING_STOP_ID),
        dropping_stop_id=UUID(DROPPING_STOP_ID),
    )
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
        "seat_id": SEAT_ID,
        "seat_number": SEAT_NUMBER,
        "hold_id": str(hold["id"]),
        "hold_expires_at": hold["expires_at"].isoformat(),
    }


def stage_pending_booking(config: dict[str, Any], context: BookingContext, passenger_args: dict[str, Any]):
    """Helper to stage pending booking action and pause at approval_node interrupt."""
    pending_action = build_pending_booking_action(context, passenger_args)
    staged_context = context.copy()
    staged_context["passenger_name"] = passenger_args["passenger_name"]
    staged_context["passenger_age"] = passenger_args["passenger_age"]
    staged_context["passenger_gender"] = passenger_args["passenger_gender"]

    init_state: AgentState = {
        "user_id": str(config["configurable"]["current_user"].id),
        "user_message": "Confirm booking",
        "memories": [],
        "booking_context": staged_context,
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
        "iteration": 0,
        "error": "",
        "pending_action": pending_action,
        "approval_status": "pending",
    }
    graph.update_state(config, init_state, as_node="llm")
    interrupted_res = graph.invoke(None, config=config)
    assert "__interrupt__" in interrupted_res
    return pending_action


def test_validate_booking_arguments():
    """Test 1: Passenger arguments validation rejects invalid data and extra fields."""
    valid_args = {
        "passenger_name": "John Doe",
        "passenger_age": 30,
        "passenger_gender": "Male",
    }
    validated = validate_booking_arguments(valid_args)
    assert validated["passenger_name"] == "John Doe"
    assert validated["passenger_age"] == 30
    assert validated["passenger_gender"] == "MALE"

    # Extra fields forbidden
    with pytest.raises(BookingActionError):
        validate_booking_arguments({**valid_args, "hold_id": "fake_id"})

    # Invalid age
    with pytest.raises(BookingActionError):
        validate_booking_arguments({**valid_args, "passenger_age": -5})

    # Empty name
    with pytest.raises(BookingActionError):
        validate_booking_arguments({**valid_args, "passenger_name": ""})


def test_booking_without_hold_fails():
    """Test 2: Requesting booking when hold is missing fails validation."""
    context_no_hold: BookingContext = {
        "seat_id": SEAT_ID,
        "seat_number": SEAT_NUMBER,
    }
    with pytest.raises(BookingActionError, match="active seat hold is required"):
        build_pending_booking_action(
            context_no_hold,
            {"passenger_name": "John", "passenger_age": 30, "passenger_gender": "Male"},
        )


def test_booking_approval_creates_real_booking_and_payment_order(base_held_context):
    """
    Test 3: Approving the pending booking action creates a PAYMENT_PENDING booking
    and Razorpay payment record in DB, and updates context with booking and payment order.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

    # Stage state and interrupt
    stage_pending_booking(
        config=config,
        context=base_held_context,
        passenger_args={"passenger_name": "John Doe", "passenger_age": 30, "passenger_gender": "Male"},
    )

    # Resume with approval
    result = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )

    # Verify context updates
    ctx = result.get("booking_context", {})
    booking_id = ctx.get("booking_id")
    assert booking_id is not None
    assert ctx.get("booking_reference", "").startswith("BUS-")
    assert ctx.get("booking_status") == "PAYMENT_PENDING"
    assert ctx.get("total_amount") is not None
    assert ctx.get("payment_id") is not None
    assert ctx.get("payment_order_id", "").startswith("order_")
    assert ctx.get("payment_order_amount") is not None
    assert result.get("approval_status") == "executed"

    # Verify rows in PostgreSQL
    conn_info = (
        f"host={os.getenv('host')} "
        f"port={os.getenv('port')} "
        f"dbname={os.getenv('dbname')} "
        f"user={os.getenv('user')} "
        f"password={os.getenv('password')}"
    )
    with connect(conn_info, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Check booking
            cur.execute(
                "SELECT id, status, auth_user_id, total_amount FROM bookings WHERE id = %s;",
                (UUID(booking_id),),
            )
            b_row = cur.fetchone()
            assert b_row is not None
            assert b_row["status"] == "PAYMENT_PENDING"
            assert b_row["auth_user_id"] == TEST_USER_ID

            # Check booking_seats
            cur.execute(
                "SELECT passenger_name, passenger_age, passenger_gender FROM booking_seats WHERE booking_id = %s;",
                (UUID(booking_id),),
            )
            s_row = cur.fetchone()
            assert s_row is not None
            assert s_row["passenger_name"] == "John Doe"
            assert s_row["passenger_age"] == 30
            assert s_row["passenger_gender"] == "MALE"

            # Check payments
            cur.execute(
                "SELECT id, provider, status, provider_order_id FROM payments WHERE booking_id = %s;",
                (UUID(booking_id),),
            )
            p_row = cur.fetchone()
            assert p_row is not None
            assert p_row["provider"] == "razorpay"
            assert p_row["status"] == "CREATED"


def test_booking_rejection_cancels_action_keeps_hold(base_held_context):
    """
    Test 4: Rejecting booking clears pending action, preserves seat hold, and creates no booking rows.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

    stage_pending_booking(
        config=config,
        context=base_held_context,
        passenger_args={"passenger_name": "Jane Doe", "passenger_age": 28, "passenger_gender": "Female"},
    )

    result = run_agent(
        current_user=TEST_USER,
        user_message="reject",
        thread_id=thread_id,
        approval_decision="reject",
    )

    assert result.get("approval_status") == "rejected"
    assert result.get("pending_action") is None
    assert "cancelled" in result.get("final_response", "").lower()

    # Verify no booking was created
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
                "SELECT COUNT(*) as count FROM bookings WHERE auth_user_id = %s;",
                (TEST_USER_ID,),
            )
            row = cur.fetchone()
            assert row["count"] == 0

            # Hold should still be ACTIVE
            cur.execute(
                "SELECT status FROM seat_holds WHERE id = %s;",
                (UUID(base_held_context["hold_id"]),),
            )
            h_row = cur.fetchone()
            assert h_row is not None
            assert h_row["status"] == "ACTIVE"


def test_booking_idempotent_approval_replay(base_held_context):
    """
    Test 5: Resubmitting 'approve' on an already executed booking returns existing booking confirmation
    without creating duplicate bookings.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

    # Stage state and interrupt
    stage_pending_booking(
        config=config,
        context=base_held_context,
        passenger_args={"passenger_name": "John Doe", "passenger_age": 30, "passenger_gender": "Male"},
    )

    # Turn 1: Approve
    res1 = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )
    booking_id_1 = res1.get("booking_context", {}).get("booking_id")
    assert booking_id_1 is not None

    # Turn 2: Replay approve
    res2 = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )
    assert res2.get("approval_status") == "executed"
    assert "already been created" in res2.get("final_response", "").lower()
    booking_id_2 = res2.get("booking_context", {}).get("booking_id")
    assert booking_id_1 == booking_id_2


def test_booking_fails_if_hold_expired(base_held_context):
    """
    Test 6: Booking approval fails if the seat hold expires before approval.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

    # Stage state and interrupt
    stage_pending_booking(
        config=config,
        context=base_held_context,
        passenger_args={"passenger_name": "John Doe", "passenger_age": 30, "passenger_gender": "Male"},
    )

    # Now expire the hold in database
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
                "UPDATE seat_holds SET created_at = CURRENT_TIMESTAMP - INTERVAL '11 minutes', expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute' WHERE id = %s;",
                (UUID(base_held_context["hold_id"]),),
            )
        conn.commit()

    result = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )

    assert result.get("approval_status") == "failed"
    assert "expired" in result.get("final_response", "").lower()


def test_fastapi_endpoints_for_booking(base_held_context):
    """
    Test 7: Test /api/v1/chat/approval returns booking and payment order info in payload.
    """
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    try:
        conversation_id = str(uuid.uuid4())
        thread_id = f"{TEST_USER_ID}:{conversation_id}"
        config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

        stage_pending_booking(
            config=config,
            context=base_held_context,
            passenger_args={"passenger_name": "Alice Smith", "passenger_age": 25, "passenger_gender": "Female"},
        )

        # Set cookie and call approval endpoint
        client.cookies.set("bus_booking_conversation_id", conversation_id)
        resp = client.post(
            "/api/v1/chat/approval",
            json={"approval_decision": "approve"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "booking" in data
        assert data["booking"]["status"] == "PAYMENT_PENDING"
        assert "payment_order" in data
        assert data["payment_order"]["order_id"].startswith("order_")
    finally:
        app.dependency_overrides.clear()


def test_payment_verify_and_finalize_endpoint(base_held_context):
    """
    Test 8: Test payment verify endpoint verifies payment and confirms booking in DB.
    """
    thread_id = f"{TEST_USER_ID}:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id, "current_user": TEST_USER}}

    # Stage and approve booking
    stage_pending_booking(
        config=config,
        context=base_held_context,
        passenger_args={"passenger_name": "Bob Marley", "passenger_age": 36, "passenger_gender": "Male"},
    )

    agent_result = run_agent(
        current_user=TEST_USER,
        user_message="approve",
        thread_id=thread_id,
        approval_decision="approve",
    )
    ctx = agent_result.get("booking_context", {})
    payment_id = UUID(ctx["payment_id"])
    booking_id = UUID(ctx["booking_id"])

    # Test finalization endpoint directly
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        conn_info = (
            f"host={os.getenv('host')} "
            f"port={os.getenv('port')} "
            f"dbname={os.getenv('dbname')} "
            f"user={os.getenv('user')} "
            f"password={os.getenv('password')}"
        )
        # Mark payment SUCCESS so finalize_booking can proceed
        with connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE payments SET status = 'SUCCESS', paid_at = CURRENT_TIMESTAMP WHERE id = %s;",
                    (payment_id,),
                )
            conn.commit()

        resp = client.post(
            "/api/v1/payment/finalize",
            json={"payment_id": str(payment_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["booking"]["status"] == "CONFIRMED"
        assert data["hold"]["status"] == "CONVERTED"

        # Verify DB rows
        with connect(conn_info, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM bookings WHERE id = %s;", (booking_id,))
                b_row = cur.fetchone()
                assert b_row["status"] == "CONFIRMED"

                cur.execute("SELECT status, booking_id FROM seat_holds WHERE id = %s;", (UUID(base_held_context["hold_id"]),))
                h_row = cur.fetchone()
                assert h_row["status"] == "CONVERTED"
                assert h_row["booking_id"] == booking_id
    finally:
        app.dependency_overrides.clear()
