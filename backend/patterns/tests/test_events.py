"""Tests for the event ingest + state update path."""
from __future__ import annotations


def test_ingest_event_creates_record_and_updates_state(client):
    payload = {
        "household_id": "H001",
        "device_id": "son_room_fan",
        "device_type": "fan",
        "room": "son_room",
        "action": "ON",
        "triggered_by": "son",
    }
    resp = client.post("/events", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["event_id"]
    assert body["device_id"] == "son_room_fan"

    state = client.get("/state/H001").json()
    assert "son_room_fan" in state["active_devices"]

    # Turning it off removes it from active devices.
    payload["action"] = "OFF"
    client.post("/events", json=payload)
    state = client.get("/state/H001").json()
    assert "son_room_fan" not in state["active_devices"]


def test_presence_event_updates_people_home(client):
    client.post("/events", json={
        "household_id": "H001",
        "device_id": "mother_presence",
        "device_type": "presence",
        "room": "entrance",
        "action": "ARRIVE",
        "triggered_by": "mother",
    })
    state = client.get("/state/H001").json()
    assert state["people_home"]["mother"] is True


def test_list_events_returns_chronological(client):
    for action in ("ON", "OFF"):
        client.post("/events", json={
            "household_id": "H001",
            "device_id": "porch_light",
            "device_type": "light",
            "room": "porch",
            "action": action,
            "triggered_by": "system",
        })
    events = client.get("/events", params={"household_id": "H001"}).json()
    assert len(events) == 2
    assert events[0]["timestamp"] <= events[1]["timestamp"]
