import uuid
import pytest
from fastapi.testclient import TestClient
from main import app, get_current_user
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
