from typing import Any
from uuid import UUID

from supabase import Client


class BookingService:
    def __init__(self, client: Client):
        self.client = client

    def history(self, user_id: UUID) -> Any:
        response = self.client.rpc(
            "booking_history",
            {"p_user_id": str(user_id)},
        ).execute()
        return response.data
