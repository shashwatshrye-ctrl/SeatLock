from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_supabase_client

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
RESERVATION_ID = "123e4567-e89b-12d3-a456-426614174001"


class FakeQuery:
    def __init__(self, client, name: str, params: dict):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.calls.append((self.name, self.params))
        data = self.client.responses.get(self.name)
        if data is not None:
            return type("Response", (), {"data": data})()

        now = datetime.now(timezone.utc)
        reservation = {
            "id": RESERVATION_ID,
            "seat_id": self.params.get("p_seat_id", 17),
            "user_id": self.params.get("p_user_id", USER_ID),
            "idempotency_key": self.params.get("p_idempotency_key", "request-1"),
            "status": "reserved",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "confirmed_at": None,
        }
        if self.name in ("reserve_seat", "get_reservation"):
            return type("Response", (), {"data": reservation})()
        if self.name == "confirm_reservation":
            reservation["status"] = "confirmed"
            reservation["expires_at"] = None
            reservation["confirmed_at"] = now.isoformat()
            return type("Response", (), {"data": reservation})()
        if self.name == "fail_payment":
            reservation["status"] = "payment_failed"
            reservation["expires_at"] = None
            return type("Response", (), {"data": reservation})()
        if self.name == "cancel_reservation":
            reservation["status"] = "cancelled"
            reservation["expires_at"] = None
            return type("Response", (), {"data": reservation})()
        return type("Response", (), {"data": []})()


class FakeClient:
    def __init__(self):
        self.calls = []
        self.responses = {}

    def rpc(self, name: str, params: dict) -> FakeQuery:
        return FakeQuery(self, name, params)


@pytest.fixture
def api_client():
    fake_client = FakeClient()
    app.dependency_overrides[get_supabase_client] = lambda: fake_client
    with TestClient(app) as test_client:
        yield test_client, fake_client
    app.dependency_overrides.clear()


def test_reserve_sends_request_to_database(api_client):
    test_client, fake_client = api_client

    response = test_client.post(
        "/reservations",
        json={
            "user_id": USER_ID,
            "seat_id": 17,
            "idempotency_key": "request-1",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "reserved"
    assert response.json()["seat_id"] == 17
    assert fake_client.calls[0][0] == "reserve_seat"
    assert fake_client.calls[0][1]["p_hold_seconds"] == 300


def test_unavailable_seat_maps_to_conflict(api_client):
    test_client, fake_client = api_client
    fake_client.responses["reserve_seat"] = {"error": "seat_unavailable"}

    response = test_client.post(
        "/reservations",
        json={
            "user_id": USER_ID,
            "seat_id": 17,
            "idempotency_key": "request-2",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "seat_unavailable"


def test_confirmation_endpoint_accepts_successful_payment(api_client):
    test_client, fake_client = api_client

    response = test_client.post(
        f"/reservations/{RESERVATION_ID}/confirm",
        json={"user_id": USER_ID, "outcome": "success"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert fake_client.calls[0][0] == "confirm_reservation"


def test_failed_payment_releases_reservation(api_client):
    test_client, fake_client = api_client

    response = test_client.post(
        f"/reservations/{RESERVATION_ID}/confirm",
        json={"user_id": USER_ID, "outcome": "failure"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "payment_failed"
    assert fake_client.calls[0][0] == "fail_payment"


def test_health_does_not_require_database(api_client):
    test_client, fake_client = api_client

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert fake_client.calls == []
