import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("ticketing.errors")

ERROR_STATUS = {
    "seat_not_found": 404,
    "reservation_not_found": 404,
    "not_found": 404,
    "seat_unavailable": 409,
    "not_reservable": 409,
    "already_final": 409,
    "payment_not_pending": 409,
    "invalid_transition": 409,
    "reservation_expired": 410,
    "invalid_hold_duration": 422,
    "database_not_configured": 503,
}


class TicketingError(Exception):
    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code or ERROR_STATUS.get(code, 500)
        super().__init__(code)


async def ticketing_error_handler(
    request: Request,
    exception: TicketingError,
) -> JSONResponse:
    if exception.status_code >= 500:
        logger.error(
            "Ticketing server error: %s on %s %s",
            exception.code,
            request.method,
            request.url.path,
        )
    return JSONResponse(
        status_code=exception.status_code,
        content={"detail": exception.code},
    )
