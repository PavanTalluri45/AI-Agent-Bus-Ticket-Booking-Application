import uuid
import pytest
from fastapi.testclient import TestClient
from main import _build_agent_payload, app, get_current_user
from bus_booking_ai_agent.auth.models import AuthenticatedUser

TEST_USER_ID = uuid.UUID("7803ebf4-7421-495d-b186-ec01c7c591c3")
TEST_USER = AuthenticatedUser(
    id=TEST_USER_ID,
    email="testuser@example.com",
    role="authenticated",
    app_metadata={},
    user_metadata={"full_name": "Test User"},
)


def test_conversations_crud_lifecycle():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    client = TestClient(app)

    try:
        # 1. Message 1 without conversation_id creates new conversation
        res = client.post(
            "/api/v1/chat",
            json={"message": "Are there any buses from Hyderabad to Bangalore tomorrow?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "conversation_id" in data
        conv_id = data["conversation_id"]

        # 2. List conversations includes the new one
        res_list = client.get("/api/v1/conversations")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["success"] is True
        found = any(c["id"] == conv_id for c in list_data["conversations"])
        assert found is True

        # 3. Retrieve conversation details
        res_detail = client.get(f"/api/v1/conversations/{conv_id}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["success"] is True
        assert detail_data["id"] == conv_id
        assert len(detail_data["messages"]) >= 2  # user + assistant

        # 4. Message 2 appends to existing conversation
        res_msg2 = client.post(
            "/api/v1/chat",
            json={
                "message": "Which one arrives the earliest?",
                "conversation_id": conv_id,
            },
        )
        assert res_msg2.status_code == 200
        assert res_msg2.json()["conversation_id"] == conv_id

        # Verify messages appended
        res_detail2 = client.get(f"/api/v1/conversations/{conv_id}")
        assert len(res_detail2.json()["messages"]) >= 4

        # 5. Rename conversation
        res_rename = client.patch(
            f"/api/v1/conversations/{conv_id}",
            json={"title": "Hyderabad Trip Plans"},
        )
        assert res_rename.status_code == 200
        assert res_rename.json()["title"] == "Hyderabad Trip Plans"

        # Verify rename in detail
        res_detail3 = client.get(f"/api/v1/conversations/{conv_id}")
        assert res_detail3.json()["title"] == "Hyderabad Trip Plans"

        # 6. Delete conversation
        res_delete = client.delete(f"/api/v1/conversations/{conv_id}")
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True

        # Verify 404 after deletion
        res_detail4 = client.get(f"/api/v1/conversations/{conv_id}")
        assert res_detail4.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_soft_delete_prevents_access_and_new_turns():
    """Verify that soft-deleted conversations cannot be fetched, renamed, or receive turns."""
    from sqlalchemy import text
    from bus_booking_ai_agent.config.database import engine

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    client = TestClient(app)

    try:
        # Create a conversation record directly
        conv_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO conversations (id, auth_user_id, title)
                    VALUES (:id, :user_id, 'Soft Delete Test')
                """),
                {"id": conv_id, "user_id": str(TEST_USER.id)},
            )

        # Soft delete via endpoint
        res_delete = client.delete(f"/api/v1/conversations/{conv_id}")
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True

        # 1. Row still exists in database with deleted_at IS NOT NULL
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT deleted_at FROM conversations WHERE id = :id"),
                {"id": conv_id},
            ).mappings().first()
            assert row is not None
            assert row["deleted_at"] is not None

        # 2. GET returns 404
        assert client.get(f"/api/v1/conversations/{conv_id}").status_code == 404

        # 3. PATCH rename returns 404
        assert client.patch(
            f"/api/v1/conversations/{conv_id}",
            json={"title": "Should Fail"},
        ).status_code == 404

        # 4. GET /conversations excludes it
        res_list = client.get("/api/v1/conversations")
        assert res_list.status_code == 200
        assert not any(c["id"] == conv_id for c in res_list.json()["conversations"])

        # 5. POST /chat with this soft-deleted conversation_id returns 404
        res_chat = client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": conv_id},
        )
        assert res_chat.status_code == 404
        assert "not found or access denied" in res_chat.json()["detail"].lower()

    finally:
        app.dependency_overrides.clear()


def test_conversation_turns_pending_and_ordering():
    """Verify pending turn creation, safe concurrent turn numbering, and Option A expansion."""
    from sqlalchemy import text
    from bus_booking_ai_agent.config.database import engine
    from main import _create_pending_turn, _complete_turn

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    client = TestClient(app)

    try:
        conv_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO conversations (id, auth_user_id, title)
                    VALUES (:id, :user_id, 'Turn Order Test')
                """),
                {"id": conv_id, "user_id": str(TEST_USER.id)},
            )

        # 1. Create Turn 1 (Pending)
        turn_1_id = _create_pending_turn(conv_id, "Where is the bus?")
        with engine.connect() as conn:
            t1 = conn.execute(
                text("SELECT turn_number, user_message, assistant_message FROM conversation_turns WHERE id = :id"),
                {"id": turn_1_id},
            ).mappings().first()
            assert t1["turn_number"] == 1
            assert t1["user_message"] == "Where is the bus?"
            assert t1["assistant_message"] is None

        # Check Option A expansion for pending turn: only user message is exposed
        res_pending = client.get(f"/api/v1/conversations/{conv_id}")
        assert res_pending.status_code == 200
        messages = res_pending.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Where is the bus?"

        # 2. Complete Turn 1
        seat_map = {
            "bus_type": "AC Seater",
            "selected_seat": None,
            "seats": [
                {
                    "seat_number": "1A",
                    "seat_type": "SEATER",
                    "row_number": 1,
                    "column_number": 1,
                    "status": "available",
                }
            ],
        }
        _complete_turn(
            turn_1_id,
            conv_id,
            "The bus is at Hyderabad station.",
            {"verified": True, "seat_map": seat_map},
        )
        with engine.connect() as conn:
            t1_after = conn.execute(
                text("SELECT assistant_message, metadata FROM conversation_turns WHERE id = :id"),
                {"id": turn_1_id},
            ).mappings().first()
            assert t1_after["assistant_message"] == "The bus is at Hyderabad station."

        # Check Option A expansion after completion: both user and assistant exposed
        res_completed = client.get(f"/api/v1/conversations/{conv_id}")
        messages = res_completed.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Where is the bus?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "The bus is at Hyderabad station."
        assert messages[1]["metadata"]["seat_map"] == seat_map

        # 3. Create Turn 2: verifies deterministic ordering (turn_number == 2)
        turn_2_id = _create_pending_turn(conv_id, "What is the departure time?")
        with engine.connect() as conn:
            t2 = conn.execute(
                text("SELECT turn_number, user_message FROM conversation_turns WHERE id = :id"),
                {"id": turn_2_id},
            ).mappings().first()
            assert t2["turn_number"] == 2
            assert t2["user_message"] == "What is the departure time?"

        _complete_turn(turn_2_id, conv_id, "It departs at 9:00 PM.")

        res_two_turns = client.get(f"/api/v1/conversations/{conv_id}")
        assert len(res_two_turns.json()["messages"]) == 4

    finally:
        app.dependency_overrides.clear()


def test_agent_payload_includes_only_current_uuid_free_seat_map():
    result = {
        "final_response": "Choose an available seat.",
        "booking_context": {
            "bus_type": "AC Seater",
            "boarding_stop_id": "boarding-id",
            "dropping_stop_id": "dropping-id",
            "seat_map_segment": "boarding-id:dropping-id",
            "seat_map_fresh": True,
            "seat_number": "1B",
            "hold_id": "hold-id",
            "seat_map": [
                {
                    "seat_id": "internal-seat-uuid",
                    "seat_number": "1B",
                    "seat_type": "SEATER",
                    "row_number": 1,
                    "column_number": 2,
                    "status": "unavailable",
                },
                {
                    "seat_id": "another-internal-seat-uuid",
                    "seat_number": "1A",
                    "seat_type": "SEATER",
                    "row_number": 1,
                    "column_number": 1,
                    "status": "available",
                },
            ],
        },
    }

    payload, metadata = _build_agent_payload(result, "conversation-id")

    assert payload["seat_map"]["selected_seat"] == "1B"
    assert payload["seat_map"]["seats"][0]["status"] == "held_by_you"
    assert payload["seat_map"]["seats"][1]["status"] == "available"
    assert "seat_id" not in str(payload["seat_map"])
    assert metadata["seat_map"] == payload["seat_map"]

    result["booking_context"]["seat_map_segment"] = "old:segment"
    stale_payload, stale_metadata = _build_agent_payload(result, "conversation-id")
    assert "seat_map" not in stale_payload
    assert "seat_map" not in stale_metadata

    result["booking_context"]["seat_map_segment"] = "boarding-id:dropping-id"
    result["booking_context"]["booking_id"] = "booking-id"
    booked_payload, booked_metadata = _build_agent_payload(result, "conversation-id")
    assert "seat_map" not in booked_payload
    assert "seat_map" not in booked_metadata


def test_empty_available_list_does_not_hide_full_unavailable_map():
    payload, metadata = _build_agent_payload(
        {
            "final_response": "No seats are available.",
            "booking_context": {
                "bus_type": "AC Seater",
                "boarding_stop_id": "boarding-id",
                "dropping_stop_id": "dropping-id",
                "seat_map_segment": "boarding-id:dropping-id",
                "seat_map_fresh": True,
                "available_seats": [],
                "seat_map": [
                    {
                        "seat_id": "seat-1",
                        "seat_number": "1A",
                        "seat_type": "SEATER",
                        "row_number": 1,
                        "column_number": 1,
                        "status": "unavailable",
                    },
                    {
                        "seat_id": "seat-2",
                        "seat_number": "1B",
                        "seat_type": "SEATER",
                        "row_number": 1,
                        "column_number": 2,
                        "status": "unavailable",
                    },
                ],
            },
        },
        "conversation-id",
    )

    assert len(payload["seat_map"]["seats"]) == 2
    assert {seat["status"] for seat in payload["seat_map"]["seats"]} == {
        "unavailable"
    }
    assert metadata["seat_map"] == payload["seat_map"]


def test_seat_map_is_attached_only_on_the_availability_turn():
    """The map must not follow the conversation into every later response."""
    context = {
        "bus_type": "AC Seater",
        "boarding_stop_id": "boarding-id",
        "dropping_stop_id": "dropping-id",
        "seat_map_segment": "boarding-id:dropping-id",
        "seat_map": [
            {
                "seat_id": "seat-1",
                "seat_number": "1A",
                "seat_type": "SEATER",
                "row_number": 1,
                "column_number": 1,
                "status": "available",
            }
        ],
    }

    # Turn that checked availability: the map is attached.
    fresh_payload, fresh_metadata = _build_agent_payload(
        {
            "final_response": "Here are the seats.",
            "booking_context": {**context, "seat_map_fresh": True},
        },
        "conversation-id",
    )
    assert fresh_payload["seat_map"]["seats"][0]["seat_number"] == "1A"
    assert fresh_payload["selected_seat"] is None
    assert fresh_metadata["seat_map"] == fresh_payload["seat_map"]

    # Later turns (seat chosen, hold requested, passenger details...): no map,
    # but the resolved seat is still reported so the UI can highlight it.
    later_payload, later_metadata = _build_agent_payload(
        {
            "final_response": "Seat 1A selected.",
            "booking_context": {**context, "seat_number": "1A"},
        },
        "conversation-id",
    )
    assert "seat_map" not in later_payload
    assert "seat_map" not in later_metadata
    assert later_payload["selected_seat"] == "1A"
    assert later_metadata["selected_seat"] == "1A"

    # Before boarding and dropping are chosen there is no seat-selection phase.
    early_payload, _ = _build_agent_payload(
        {
            "final_response": "Where will you board?",
            "booking_context": {"bus_type": "AC Seater"},
        },
        "conversation-id",
    )
    assert "seat_map" not in early_payload
    assert "selected_seat" not in early_payload
