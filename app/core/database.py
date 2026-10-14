from functools import lru_cache
from supabase import Client, create_client
from app.core.errors import TicketingError
from app.core.settings import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise TicketingError(
            "database_not_configured",
            status_code=503,
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
