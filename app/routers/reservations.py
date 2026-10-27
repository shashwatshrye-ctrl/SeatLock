from fastapi import APIRouter, Query, status

from app.routers.dependencies import ReservationServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.reservations import (
    PaymentRequest,
    ReservationAction,
    ReservationCreate,
    ReservationResponse,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve a concert seat",
    description=(
        "Places an atomic temporary hold on a seat for the student. "
        "Requires only `seat_id` and `user_id`. Guarantees no double-booking."
    ),
    responses={
        status.HTTP_201_CREATED: {"description": "Seat successfully reserved."},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Seat ID does not exist."},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Seat already reserved or confirmed by another user."},
        422: {"description": "Validation error or invalid hold duration."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Database connection not configured."},
    },
)
def reserve_seat(
    request: ReservationCreate,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return service.reserve(request)


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get reservation status",
    description="Fetches current status of a reservation. Automatically returns 'expired' if hold has lapsed.",
    responses={
        status.HTTP_200_OK: {"description": "Reservation details returned."},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Reservation not found."},
    },
)
def reservation_status(
    reservation_id: int,
    service: ReservationServiceDependency,
    user_id: int | None = Query(default=None, description="Optional user ID"),
) -> ReservationResponse:
    return service.get_status(reservation_id, user_id)


@router.post(
    "/{reservation_id}/confirm",
    response_model=ReservationResponse,
    summary="Confirm or fail booking with simulated payment",
    description=(
        "Simulates payment processing. Requires only `user_id` (outcome defaults to 'success')."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Payment processed and reservation status updated."},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Reservation not found."},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Reservation not in reservable/pending state."},
        status.HTTP_410_GONE: {"model": ErrorResponse, "description": "Reservation has expired and seat was released."},
    },
)
async def confirm_reservation(
    reservation_id: int,
    request: PaymentRequest,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return await service.process_payment(
        reservation_id,
        request.user_id,
        request.outcome,
        request.delay_seconds,
    )


@router.post(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
    summary="Cancel reservation or booking",
    description="Allows a student to voluntarily cancel an active hold or confirmed booking, immediately freeing the seat.",
    responses={
        status.HTTP_200_OK: {"description": "Reservation cancelled and seat released."},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Reservation not found."},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Invalid state transition for cancellation."},
    },
)
def cancel_reservation(
    reservation_id: int,
    request: ReservationAction,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return service.cancel(reservation_id, request.user_id)
