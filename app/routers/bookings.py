from uuid import UUID

from fastapi import APIRouter

from app.routers.dependencies import BookingServiceDependency
from app.schemas.reservations import ReservationResponse

router = APIRouter(prefix="/users", tags=["bookings"])


@router.get("/{user_id}/bookings", response_model=list[ReservationResponse])
def booking_history(
    user_id: UUID,
    service: BookingServiceDependency,
) -> list[ReservationResponse]:
    return service.history(user_id)
