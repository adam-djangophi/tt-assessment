from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator
from pydantic.alias_generators import to_camel

from app.enums import (
    BenchmarkPosition,
    ChangeOrderStatus,
    CreateChangeOrderStatus,
    ProjectStatus,
    RagStatus,
)

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base model: snake_case fields, camelCase JSON (from FastAPI OpenAPI export)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
    )


class Project(CamelModel):
    """Summary representation of a portfolio project."""

    id: str
    name: str
    region: str
    sector: str
    status: ProjectStatus
    start_date: date
    planned_end_date: date
    baseline_cost: float
    currency: str


class ProjectDetail(Project):
    """Extended project view with computed cost and schedule KPIs."""

    actual_cost_to_date: float
    cost_variance: float
    schedule_slippage_days: int
    open_change_order_count: int


class CostSnapshot(CamelModel):
    """A single month's baseline, forecast, and actual cost figures."""

    period_month: date
    work_package_id: str | None = None
    baseline_cost: float
    forecast_cost: float
    actual_cost: float


class Milestone(CamelModel):
    """A schedule milestone with dates and RAG status."""

    id: str
    name: str
    planned_date: date
    forecast_date: date | None = None
    actual_date: date | None = None
    rag_status: RagStatus


class ChangeOrder(CamelModel):
    """A change order with cost and schedule impact."""

    id: str
    work_package_id: str | None = None
    work_package_code: str | None = None
    reference: str
    title: str
    status: ChangeOrderStatus
    cost_delta: float
    schedule_delta_days: int
    raised_date: date


class ChangeOrderCreate(CamelModel):
    """Request body for creating a new change order."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work_package_code: str = Field(min_length=1, max_length=50)
    status: CreateChangeOrderStatus = CreateChangeOrderStatus.DRAFT
    reference: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    cost_delta: Annotated[
        Decimal,
        Field(gt=0, max_digits=14, decimal_places=2),
        WithJsonSchema({"type": "number", "exclusiveMinimum": 0}),
    ]
    schedule_delta_days: int = Field(gt=0, le=3650, strict=True)
    raised_date: date = Field(default_factory=date.today)

    @field_validator("raised_date")
    @classmethod
    def not_in_future(cls, v: date) -> date:
        # The server runs in UTC; a planner in a timezone ahead of UTC may already be on
        # tomorrow's date, so allow one day of slack rather than reject their "today".
        if v > date.today() + timedelta(days=1):
            raise ValueError("raisedDate cannot be in the future")
        return v

    @field_validator("reference", "work_package_code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        """Codes are case-insensitive; store them upper-cased so 'co-001' == 'CO-001'."""
        return v.upper()


class PaginatedResponse(CamelModel, Generic[T]):
    """Paginated list wrapper with total count and paging metadata."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ChangeOrderList(PaginatedResponse[ChangeOrder]):
    """Paginated change order list."""


class BenchmarkComparison(CamelModel):
    """A project's unit-cost metric compared against sector/region peer distribution."""

    metric_key: str
    unit: str
    project_value: float
    peer_median: float
    peer_p25: float
    peer_p75: float
    position: BenchmarkPosition


class ErrorResponse(CamelModel):
    """Standard error response body."""

    detail: str
