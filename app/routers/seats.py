from fastapi import APIRouter, Query, status

from app.routers.dependencies import SeatServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.seats import SeatResponse

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get(
    "",
    response_model=list[SeatResponse],
    summary="List concert seats",
    description="Retrieves all 500 concert seats. Pass `available_only=true` to filter only currently unreserved seats.",
    responses={
        status.HTTP_200_OK: {"description": "List of seats with real-time availability status."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Database connection not configured."},
    },
)
def list_seats(
    service: SeatServiceDependency,
    available_only: bool = Query(
        default=False,
        description="Filter to return only unbooked, unreserved seats",
    ),
) -> list[SeatResponse]:
    return service.list_seats(available_only=available_only)
