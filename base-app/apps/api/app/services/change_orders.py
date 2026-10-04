"""Write-side business rules for change orders.

Raises domain errors only; routers translate them into HTTP responses.
"""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ChangeOrder, Project, WorkPackage
from app.enums import ProjectStatus
from app.schemas import ChangeOrderCreate

# "A planner working a live project": change orders are only raised once a project is in delivery.
RAISABLE_PROJECT_STATUSES = {ProjectStatus.IN_DELIVERY}


class ProjectNotLive(Exception):
    """The project is not in a state where change orders can be raised."""

    def __init__(self, status: str) -> None:
        super().__init__(f"Change orders can only be raised on live projects; this is '{status}'")


class WorkPackageNotInProject(Exception):
    """The named work package code does not exist on this project."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Work package '{code}' does not belong to this project")


class DuplicateReference(Exception):
    """A change order with this reference already exists on this project."""

    def __init__(self, reference: str) -> None:
        super().__init__(f"Reference '{reference}' already exists on this project")


def _resolve_work_package_id(db: Session, project: Project, code: str) -> str:
    """Map a work package code to its id, scoped to the project."""
    work_package_id = db.scalar(
        select(WorkPackage.id).where(
            WorkPackage.project_id == project.id,
            WorkPackage.code == code,
        )
    )
    if work_package_id is None:
        raise WorkPackageNotInProject(code)
    return work_package_id


def _reference_exists(db: Session, project: Project, reference: str) -> bool:
    existing = db.scalar(
        select(ChangeOrder.id).where(
            ChangeOrder.project_id == project.id,
            ChangeOrder.reference == reference,
        )
    )
    return existing is not None


def _is_unique_violation(error: IntegrityError) -> bool:
    """True for unique-constraint failures only (not e.g. foreign-key failures).

    Postgres reports SQLSTATE 23505; SQLite (used by the tests) only says so in the message.
    """
    return getattr(error.orig, "pgcode", None) == "23505" or "UNIQUE constraint failed" in str(
        error.orig
    )


def raise_change_order(db: Session, project: Project, data: ChangeOrderCreate) -> ChangeOrder:
    """Check the request against existing project data, then persist the change order."""
    if project.status not in RAISABLE_PROJECT_STATUSES:
        raise ProjectNotLive(project.status)
    work_package_id = _resolve_work_package_id(db, project, data.work_package_code)
    if _reference_exists(db, project, data.reference):
        raise DuplicateReference(data.reference)

    change_order = ChangeOrder(
        id=str(uuid4()),
        project_id=project.id,
        work_package_id=work_package_id,
        reference=data.reference,
        title=data.title,
        status=data.status,
        cost_delta=data.cost_delta,
        schedule_delta_days=data.schedule_delta_days,
        raised_date=data.raised_date,
    )
    db.add(change_order)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # Two requests raced past the duplicate check; the DB unique constraint is the backstop.
        if _is_unique_violation(error):
            raise DuplicateReference(data.reference) from None
        raise  # anything else (e.g. a referenced row vanished) is a genuine server error
    db.refresh(change_order)
    return change_order
