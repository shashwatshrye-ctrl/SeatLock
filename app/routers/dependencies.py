from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.core.database import get_supabase_client
from app.core.settings import Settings, get_settings
from app.services.bookings import BookingService
from app.services.reservations import ReservationService
from app.services.seats import SeatService

SupabaseClient = Annotated[Client, Depends(get_supabase_client)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_seat_service(client: SupabaseClient) -> SeatService:
    return SeatService(client)


def get_reservation_service(
    client: SupabaseClient,
    settings: AppSettings,
) -> ReservationService:
    return ReservationService(client, settings.reservation_hold_seconds)


def get_booking_service(client: SupabaseClient) -> BookingService:
    return BookingService(client)


SeatServiceDependency = Annotated[SeatService, Depends(get_seat_service)]
ReservationServiceDependency = Annotated[
    ReservationService,
    Depends(get_reservation_service),
]
BookingServiceDependency = Annotated[BookingService, Depends(get_booking_service)]
