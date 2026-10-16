import asyncio
import logging
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.errors import TicketingError
from app.schemas.reservations import PaymentOutcome, ReservationCreate

logger = logging.getLogger("ticketing.reservations")


class ReservationService:
    def __init__(self, client: Client, hold_seconds: int):
        self.client = client
        self.hold_seconds = hold_seconds

    def _rpc(self, name: str, params: dict[str, Any]) -> Any:
        try:
            data = self.client.rpc(name, params).execute().data
        except TicketingError:
            raise
        except Exception as exc:
            logger.error("RPC %s failed with params %s: %s", name, params, exc)
            raise TicketingError("database_error", status_code=500) from exc

        if isinstance(data, dict) and "error" in data:
            raise TicketingError(data["error"])
        return data

    def reserve(self, request: ReservationCreate) -> Any:
        return self._rpc(
            "reserve_seat",
            {
                "p_user_id": str(request.user_id),
                "p_seat_id": request.seat_id,
                "p_idempotency_key": request.idempotency_key,
                "p_hold_seconds": self.hold_seconds,
            },
        )

    def get_status(self, reservation_id: UUID, user_id: UUID) -> Any:
        return self._rpc(
            "get_reservation",
            {
                "p_reservation_id": str(reservation_id),
                "p_user_id": str(user_id),
            },
        )

    async def process_payment(
        self,
        reservation_id: UUID,
        user_id: UUID,
        outcome: PaymentOutcome,
        delay_seconds: int,
    ) -> Any:
        if outcome == PaymentOutcome.delayed:
            await asyncio.sleep(delay_seconds)

        rpc_name = (
            "fail_payment"
            if outcome == PaymentOutcome.failure
            else "confirm_reservation"
        )
        # Offload synchronous RPC call to threadpool so event loop remains non-blocking
        return await asyncio.to_thread(
            self._rpc,
            rpc_name,
            {
                "p_reservation_id": str(reservation_id),
                "p_user_id": str(user_id),
            },
        )

    def cancel(self, reservation_id: UUID, user_id: UUID) -> Any:
        return self._rpc(
            "cancel_reservation",
            {
                "p_reservation_id": str(reservation_id),
                "p_user_id": str(user_id),
            },
        )
