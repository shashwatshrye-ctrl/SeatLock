from uuid import UUID

from fastapi import APIRouter, Query, status

from app.routers.dependencies import ReservationServiceDependency
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
)
def reserve_seat(
    request: ReservationCreate,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return service.reserve(request)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def reservation_status(
    reservation_id: UUID,
    service: ReservationServiceDependency,
    user_id: UUID = Query(...),
) -> ReservationResponse:
    return service.get_status(reservation_id, user_id)


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_reservation(
    reservation_id: UUID,
    request: PaymentRequest,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return await service.process_payment(
        reservation_id,
        request.user_id,
        request.outcome,
        request.delay_seconds,
    )


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: UUID,
    request: ReservationAction,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    return service.cancel(reservation_id, request.user_id)
