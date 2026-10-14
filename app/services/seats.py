from typing import Any

from supabase import Client


class SeatService:
    def __init__(self, client: Client):
        self.client = client

    def list_seats(self, available_only: bool = False) -> Any:
        response = self.client.rpc(
            "list_seats",
            {"p_available_only": available_only},
        ).execute()
        return response.data
