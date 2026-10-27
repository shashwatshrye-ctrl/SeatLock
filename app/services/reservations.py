import asyncio
import logging
import time
from typing import Any

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
        idempotency_key = (
            request.idempotency_key
            or f"auto-{request.user_id}-{request.seat_id}-{int(time.time() * 1000)}"
        )
        return self._rpc(
            "reserve_seat",
            {
                "p_user_id": request.user_id,
                "p_seat_id": request.seat_id,
                "p_idempotency_key": idempotency_key,
                "p_hold_seconds": self.hold_seconds,
            },
        )

    def get_status(self, reservation_id: int, user_id: int | None = None) -> Any:
        params: dict[str, Any] = {"p_reservation_id": reservation_id}
        if user_id is not None:
            params["p_user_id"] = user_id
        return self._rpc("get_reservation", params)

    async def process_payment(
        self,
        reservation_id: int,
        user_id: int,
        outcome: PaymentOutcome,
        delay_seconds: int,
    ) -> Any:
        if outcome == PaymentOutcome.delayed and delay_seconds > 0:
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
                "p_reservation_id": reservation_id,
                "p_user_id": user_id,
            },
        )

    def cancel(self, reservation_id: int, user_id: int) -> Any:
        return self._rpc(
            "cancel_reservation",
            {
                "p_reservation_id": reservation_id,
                "p_user_id": user_id,
            },
        )
