"""Unit tests for the change order service: business rules without the HTTP layer."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import ChangeOrder, Project
from app.schemas import ChangeOrderCreate
from app.services import change_orders as service
from app.services.change_orders import (
    DuplicateReference,
    ProjectNotLive,
    WorkPackageNotInProject,
    raise_change_order,
)
from tests.conftest import METRO_ID


@pytest.fixture
def db(client) -> Iterator[Session]:
    """Session on the seeded test DB; depending on `client` guarantees startup seeding ran."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def metro(db: Session) -> Project:
    project = db.get(Project, METRO_ID)
    assert project is not None
    return project


def _data(**overrides: Any) -> ChangeOrderCreate:
    fields: dict[str, Any] = {
        "reference": f"CO-U-{uuid4().hex[:8]}",
        "work_package_code": "WP-01",
        "title": "Unit test change",
        "cost_delta": Decimal("2500.00"),
        "schedule_delta_days": 4,
        "raised_date": date(2025, 1, 15),
    }
    fields.update(overrides)
    return ChangeOrderCreate(**fields)


def test_save_when_linked_to_work_package(db, metro):
    created = raise_change_order(db, metro, _data(work_package_code="WP-02"))

    db.expire_all()  # force a re-read from the DB, not the identity map
    saved = db.get(ChangeOrder, created.id)
    assert saved is not None
    assert saved.project_id == METRO_ID
    assert saved.work_package_code == "WP-02"
    assert saved.status == "draft"
    assert saved.cost_delta == Decimal("2500.00")


def test_work_package_ownership_enforced(db, metro):
    with pytest.raises(WorkPackageNotInProject, match="WP-03"):
        raise_change_order(db, metro, _data(work_package_code="WP-03"))


def test_duplicate_reference_error(db, metro):
    first = raise_change_order(db, metro, _data())
    with pytest.raises(DuplicateReference, match=first.reference):
        raise_change_order(db, metro, _data(reference=first.reference))


def test_unique_constraint_backstops_racing_duplicate(db, metro, monkeypatch):
    # Simulate two requests passing the pre-check at once: skip it, so only the DB constraint
    # stands between us and a duplicate.
    monkeypatch.setattr(service, "_reference_exists", lambda *_: False)
    first = raise_change_order(db, metro, _data())

    with pytest.raises(DuplicateReference):
        raise_change_order(db, metro, _data(reference=first.reference))

    # The session was rolled back cleanly and is still usable.
    assert db.get(Project, METRO_ID) is not None


def test_non_unique_integrity_error_is_not_reported_as_duplicate(db, metro, monkeypatch):
    # e.g. the work package is deleted between the lookup and the commit: a foreign-key failure
    # must surface as itself, not be mislabelled as a duplicate reference.
    monkeypatch.setattr(service, "_resolve_work_package_id", lambda *_: "missing-wp-id")

    with pytest.raises(IntegrityError):
        raise_change_order(db, metro, _data())

    assert db.get(Project, METRO_ID) is not None


@pytest.mark.parametrize("status", ["planning", "on_hold", "complete"])
def test_only_live_projects_accept_change_orders(db, status):
    # Unsaved project: the status check runs before any query, so no seeded data is touched.
    project = Project(id="not-live", status=status)
    with pytest.raises(ProjectNotLive, match=status):
        raise_change_order(db, project, _data())
