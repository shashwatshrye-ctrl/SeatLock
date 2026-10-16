import logging
from typing import Any

from supabase import Client

from app.core.errors import TicketingError

logger = logging.getLogger("ticketing.seats")


class SeatService:
    def __init__(self, client: Client):
        self.client = client

    def list_seats(self, available_only: bool = False) -> Any:
        try:
            response = self.client.rpc(
                "list_seats",
                {"p_available_only": available_only},
            ).execute()
            data = response.data
            if isinstance(data, dict) and "error" in data:
                raise TicketingError(data["error"])
            return data or []
        except TicketingError:
            raise
        except Exception as exc:
            logger.error("list_seats RPC failed: %s", exc)
            raise TicketingError("database_error", status_code=500) from exc
