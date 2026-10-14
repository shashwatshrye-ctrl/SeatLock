import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    supabase_url: str | None
    supabase_service_role_key: str | None
    reservation_hold_seconds: int


@lru_cache
def get_settings() -> Settings:
    hold_seconds = int(os.getenv("RESERVATION_HOLD_SECONDS", "300"))
    if not 1 <= hold_seconds <= 900:
        raise ValueError("RESERVATION_HOLD_SECONDS must be between 1 and 900.")

    return Settings(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        reservation_hold_seconds=hold_seconds,
    )
