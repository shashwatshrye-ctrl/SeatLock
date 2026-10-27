from fastapi import APIRouter, status

from app.routers.dependencies import BookingServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.reservations import ReservationResponse

router = APIRouter(prefix="/users", tags=["bookings"])


@router.get(
    "/{user_id}/bookings",
    response_model=list[ReservationResponse],
    summary="Get user booking history",
    description="Returns all reservations and bookings placed by the student, ordered by most recent first.",
    responses={
        status.HTTP_200_OK: {"description": "List of user reservations and booking history."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Database connection not configured."},
    },
)
def booking_history(
    user_id: int,
    service: BookingServiceDependency,
) -> list[ReservationResponse]:
    return service.history(user_id)
