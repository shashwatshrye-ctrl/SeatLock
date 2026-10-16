import logging
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.errors import TicketingError

logger = logging.getLogger("ticketing.bookings")


class BookingService:
    def __init__(self, client: Client):
        self.client = client

    def history(self, user_id: UUID) -> Any:
        try:
            response = self.client.rpc(
                "booking_history",
                {"p_user_id": str(user_id)},
            ).execute()
            data = response.data
            if isinstance(data, dict) and "error" in data:
                raise TicketingError(data["error"])
            return data or []
        except TicketingError:
            raise
        except Exception as exc:
            logger.error("booking_history RPC failed for user %s: %s", user_id, exc)
            raise TicketingError("database_error", status_code=500) from exc
