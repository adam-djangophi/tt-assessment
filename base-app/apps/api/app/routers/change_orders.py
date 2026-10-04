from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import ChangeOrder, Project
from app.enums import ChangeOrderStatus
from app.routers.deps import get_project_or_404
from app.schemas import ChangeOrder as ChangeOrderSchema
from app.schemas import ChangeOrderCreate, ErrorResponse
from app.services.change_orders import (
    DuplicateReference,
    ProjectNotLive,
    WorkPackageNotInProject,
    raise_change_order,
)

router = APIRouter(prefix="/projects", tags=["change-orders"])


@router.get(
    "/{project_id}/change-orders",
    response_model=list[ChangeOrderSchema],
    operation_id="listChangeOrders",
)
def list_change_orders(
    project: Annotated[Project, Depends(get_project_or_404)],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[ChangeOrderStatus | None, Query()] = None,
) -> list[ChangeOrder]:
    """Return change orders for a project, optionally filtered by status."""
    stmt = select(ChangeOrder).where(ChangeOrder.project_id == project.id)
    if status:
        stmt = stmt.where(ChangeOrder.status == status)
    return list(db.scalars(stmt.order_by(ChangeOrder.raised_date)))


@router.post(
    "/{project_id}/change-orders",
    response_model=ChangeOrderSchema,
    status_code=http_status.HTTP_201_CREATED,
    operation_id="createChangeOrder",
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        409: {"description": "Reference already used for this project, or project not live"},
    },
)
def create_change_order(
    project: Annotated[Project, Depends(get_project_or_404)],
    db: Annotated[Session, Depends(get_db)],
    change_order_in: ChangeOrderCreate,
) -> ChangeOrder:
    """Create a new change order for a project."""
    try:
        return raise_change_order(db, project, change_order_in)
    except WorkPackageNotInProject as e:
        raise _body_error("workPackageCode", str(e)) from None
    except DuplicateReference as e:
        raise _body_error("reference", str(e), code=http_status.HTTP_409_CONFLICT) from None
    except ProjectNotLive as e:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=[{"loc": ["path", "project_id"], "msg": str(e), "type": "value_error"}],
        ) from None


def _body_error(field: str, msg: str, code: int = 422) -> HTTPException:
    """Create an HTTPException for a specific body field error."""
    return HTTPException(
        status_code=code,
        detail=[{"loc": ["body", field], "msg": msg, "type": "value_error"}],
    )
