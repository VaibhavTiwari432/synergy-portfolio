"""Phase 0 acceptance test: storage gate splits malformed from sparse-but-valid.

POST a known-sparse chat (short, few turns) → expect 200 with chat persisted, not 422.
POST a malformed chat (no turns) → expect 422 MALFORMED reject.

This tests the Phase 0 requirement: "Never reject for sparsity — store + flag."
The completeness gate is informational, not a hard reject (absent ≠ zero, #12).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.mark.integration
async def test_ingest_sparse_chat_returns_200_not_422():
    """Sparse chat (short, few turns) should be stored, not rejected with 422."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/ingest",
            headers={"X-API-Key": "test-key"},
            json={
                "user_ref": "sparse_test_user",
                "conversation_id": "sparse_chat_1",
                "source": "chatgpt_live",
                "partner_model": {"provider": "openai", "model": "gpt-4"},
                "turns": [
                    {"role": "user", "text": "Hi", "turn_index": 0},
                    {"role": "assistant", "text": "Hello", "turn_index": 1},
                    {"role": "user", "text": "Thanks", "turn_index": 2},
                ],
                "telemetry": None,
                "metadata": None,
                # Sparse completeness info (not proven complete)
                "capture_complete": None,
                "expected_turn_count": 3,
                "captured_turn_count": 3,
            },
        )

        # Phase 0: must NOT reject sparse chats with 422
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["status"] in ("pending", "scored")
        assert "chat_id" in body


@pytest.mark.integration
async def test_ingest_malformed_chat_returns_422():
    """Malformed chat (no turns) should be rejected with 422 MALFORMED."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/ingest",
            headers={"X-API-Key": "test-key"},
            json={
                "user_ref": "malformed_test_user",
                "conversation_id": "malformed_chat_1",
                "source": "chatgpt_live",
                "partner_model": {"provider": "openai", "model": "gpt-4"},
                "turns": [],  # No turns — genuinely malformed
                "telemetry": None,
                "metadata": None,
            },
        )

        # Must reject malformed chats with 422
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        detail = response.json()
        assert "invalid capture" in str(detail).lower()


@pytest.mark.integration
async def test_ingest_incomplete_capture_returns_200_not_422():
    """Incomplete capture (proven truncated) should be stored, not rejected.

    Phase 0 change: completeness is informational. The scoring layer will flag
    it with INSUFFICIENT_SAMPLE or similar (absent ≠ zero, #12).
    """
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/ingest",
            headers={"X-API-Key": "test-key"},
            json={
                "user_ref": "incomplete_test_user",
                "conversation_id": "incomplete_chat_1",
                "source": "chatgpt_live",
                "partner_model": {"provider": "openai", "model": "gpt-4"},
                "turns": [
                    {"role": "user", "text": "Question", "turn_index": 0},
                    {"role": "assistant", "text": "Answer", "turn_index": 1},
                ],
                "telemetry": None,
                "metadata": None,
                # Proven incomplete: captured fewer than expected
                "capture_complete": False,
                "expected_turn_count": 10,
                "captured_turn_count": 2,
            },
        )

        # Phase 0: must NOT reject incomplete chats — store them
        assert response.status_code == 200, (
            f"Expected 200 (Phase 0 allows storage of incomplete captures), "
            f"got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "chat_id" in body
