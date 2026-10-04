from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest

from tests.conftest import HARBOUR_ID, METRO_ID, RIVERSIDE_ID

# Create tests write to Metro so Riverside's seeded list/count assertions stay stable.
METRO_CO_URL = f"/projects/{METRO_ID}/change-orders"
RIVERSIDE_CO_URL = f"/projects/{RIVERSIDE_ID}/change-orders"


def _new_co(**overrides: Any) -> dict[str, Any]:
    """A valid create payload with a unique reference; override fields per test."""
    co: dict[str, Any] = {
        "workPackageCode": "WP-01",
        "status": "draft",
        "reference": f"CO-T-{uuid4().hex[:8].upper()}",
        "title": "Additional ventilation shafts",
        "costDelta": 100000.0,
        "scheduleDeltaDays": 10,
        "raisedDate": "2024-01-01",
    }
    co.update(overrides)
    return co


def test_list_change_orders(client):
    res = client.get(RIVERSIDE_CO_URL)
    assert res.status_code == 200
    orders = res.json()
    assert {o["reference"] for o in orders} == {
        "CO-001",
        "CO-002",
        "CO-003",
        "CO-004",
        "CO-005",
        "CO-006",
        "CO-007",
        "CO-008",
    }
    assert "costDelta" in orders[0]
    assert "scheduleDeltaDays" in orders[0]


def test_list_change_orders_filter_status(client):
    res = client.get(RIVERSIDE_CO_URL, params={"status": "approved"})
    assert res.status_code == 200
    orders = res.json()
    assert len(orders) == 4
    assert orders[0]["reference"] == "CO-001"
    assert orders[0]["costDelta"] == 2500000.0


def test_list_change_orders_unknown_project_404(client):
    res = client.get("/projects/nope/change-orders")
    assert res.status_code == 404


def test_list_change_orders_filter_invalid_status_422(client):
    res = client.get(
        RIVERSIDE_CO_URL,
        params={"status": "not-a-status"},
    )
    assert res.status_code == 422


# POST /projects/{project_id}/change-orders test


def test_create_success(client):
    payload = _new_co()
    res = client.post(METRO_CO_URL, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert body["reference"] == payload["reference"]
    assert body["title"] == payload["title"]
    assert body["costDelta"] == 100000.0
    assert body["scheduleDeltaDays"] == 10
    assert body["status"] == "draft"
    assert body["raisedDate"] == "2024-01-01"

    listed = client.get(METRO_CO_URL).json()
    assert any(o["id"] == body["id"] for o in listed)


def test_work_package_link_success(client):
    res = client.post(METRO_CO_URL, json=_new_co(workPackageCode="WP-02"))
    assert res.status_code == 201
    body = res.json()
    assert body["workPackageCode"] == "WP-02"
    assert body["workPackageId"] is not None


def test_without_work_package_422(client):
    # Change orders roll up to the project through work packages, so one is required.
    res = client.post(METRO_CO_URL, json=_new_co(workPackageCode=None))
    assert res.status_code == 422
    assert ["body", "workPackageCode"] in [e["loc"] for e in res.json()["detail"]]


def test_create_applies_defaults(client):
    payload = _new_co()
    del payload["status"]
    del payload["raisedDate"]
    res = client.post(METRO_CO_URL, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "draft"
    assert body["raisedDate"] == date.today().isoformat()


def test_create_accepts_submitted_status(client):
    res = client.post(METRO_CO_URL, json=_new_co(status="submitted"))
    assert res.status_code == 201
    assert res.json()["status"] == "submitted"


def test_create_change_order_unknown_project_404(client):
    res = client.post("/projects/nope/change-orders", json=_new_co())
    assert res.status_code == 404
    assert res.json()["detail"] == "Project not found"


def test_create_duplicate_reference_409(client):
    payload = _new_co()
    assert client.post(METRO_CO_URL, json=payload).status_code == 201

    res = client.post(METRO_CO_URL, json=_new_co(reference=payload["reference"]))
    assert res.status_code == 409
    assert res.json()["detail"][0]["loc"] == ["body", "reference"]


def test_seeded_reference_409(client):
    # CO-001 is seeded on Riverside; WP-01 also exists there.
    res = client.post(f"/projects/{RIVERSIDE_ID}/change-orders", json=_new_co(reference="CO-001"))
    assert res.status_code == 409


def test_same_reference_other_project_ok(client):
    # References are unique per project, not globally (CO-008 is seeded on Riverside only).
    res = client.post(METRO_CO_URL, json=_new_co(reference="CO-008"))
    assert res.status_code == 201


@pytest.mark.parametrize(
    "code",
    [
        "WP-03",  # belongs to Riverside, not Metro
        "WP-99",  # does not exist anywhere
    ],
)
def test_foreign_or_unknown_work_package_422(client, code):
    res = client.post(METRO_CO_URL, json=_new_co(workPackageCode=code))
    assert res.status_code == 422
    error = res.json()["detail"][0]
    assert error["loc"] == ["body", "workPackageCode"]
    assert code in error["msg"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"costDelta": 0}, "costDelta"),
        ({"costDelta": -500}, "costDelta"),
        ({"costDelta": 1.234}, "costDelta"),
        ({"costDelta": 10**13}, "costDelta"),
        ({"scheduleDeltaDays": 0}, "scheduleDeltaDays"),
        ({"scheduleDeltaDays": -3}, "scheduleDeltaDays"),
        ({"scheduleDeltaDays": 3651}, "scheduleDeltaDays"),
        ({"scheduleDeltaDays": 3_000_000_000}, "scheduleDeltaDays"),  # would overflow Postgres int4
        ({"scheduleDeltaDays": True}, "scheduleDeltaDays"),
        ({"scheduleDeltaDays": "5"}, "scheduleDeltaDays"),
        ({"workPackageCode": ""}, "workPackageCode"),
        ({"status": "approved"}, "status"),
        ({"status": "rejected"}, "status"),
        ({"status": "not-a-status"}, "status"),
        ({"reference": ""}, "reference"),
        ({"reference": "   "}, "reference"),
        ({"title": "   "}, "title"),
        ({"raisedDate": (date.today() + timedelta(days=2)).isoformat()}, "raisedDate"),
        ({"raisedDate": "not-a-date"}, "raisedDate"),
        ({"id": "client-chosen-id"}, "id"),
    ],
)
def test_invalid_body_422(client, overrides, field):
    res = client.post(METRO_CO_URL, json=_new_co(**overrides))
    assert res.status_code == 422
    assert ["body", field] in [e["loc"] for e in res.json()["detail"]]


@pytest.mark.parametrize(
    "field", ["reference", "title", "costDelta", "scheduleDeltaDays", "workPackageCode"]
)
def test_missing_required_field_422(client, field):
    payload = _new_co()
    del payload[field]
    res = client.post(METRO_CO_URL, json=payload)
    assert res.status_code == 422
    assert ["body", field] in [e["loc"] for e in res.json()["detail"]]


def test_rejected_body_is_not_saved(client):
    before = len(client.get(METRO_CO_URL).json())
    client.post(METRO_CO_URL, json=_new_co(costDelta=0))
    client.post(METRO_CO_URL, json=_new_co(workPackageCode="WP-03"))
    assert len(client.get(METRO_CO_URL).json()) == before


def test_create_change_order_duplicate_reference_is_case_insensitive_409(client):
    # CO-001 is seeded on Metro.
    res = client.post(METRO_CO_URL, json=_new_co(reference="co-001"))
    assert res.status_code == 409


def test_create_change_order_normalises_codes(client):
    ref = f"co-t-{uuid4().hex[:8]}"
    res = client.post(METRO_CO_URL, json=_new_co(reference=ref, workPackageCode="wp-02"))
    assert res.status_code == 201
    body = res.json()
    assert body["reference"] == ref.upper()
    assert body["workPackageCode"] == "WP-02"


def test_create_change_order_accepts_tomorrow_for_timezones_ahead_of_utc(client):
    # A planner in APAC (UTC+8) is on "tomorrow" for up to 8 hours of the server's UTC day.
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = client.post(METRO_CO_URL, json=_new_co(raisedDate=tomorrow))
    assert res.status_code == 201
    assert res.json()["raisedDate"] == tomorrow


def test_create_change_order_project_not_live_409(client):
    # Harbour is seeded in `planning`; change orders are only raised on projects in delivery.
    # The body is valid, so the live check fails before Harbour's (absent) work packages matter.
    res = client.post(f"/projects/{HARBOUR_ID}/change-orders", json=_new_co())
    assert res.status_code == 409
    error = res.json()["detail"][0]
    assert error["loc"] == ["path", "project_id"]
    assert "planning" in error["msg"]


def test_create_change_order_invalid_body_on_non_live_project_422(client):
    # Body validation runs before the service, so a bad body is reported first.
    res = client.post(f"/projects/{HARBOUR_ID}/change-orders", json=_new_co(costDelta=0))
    assert res.status_code == 422
