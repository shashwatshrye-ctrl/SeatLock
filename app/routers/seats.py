from fastapi import APIRouter, Query

from app.routers.dependencies import SeatServiceDependency
from app.schemas.seats import SeatResponse

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatResponse])
def list_seats(
    service: SeatServiceDependency,
    available_only: bool = Query(default=False),
) -> list[SeatResponse]:
    return service.list_seats(available_only=available_only)
