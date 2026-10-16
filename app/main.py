import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import TicketingError, ticketing_error_handler
from app.routers import bookings, health, reservations, seats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ticketing.api")

tags_metadata = [
    {
        "name": "health",
        "description": "Liveness and service status checks.",
    },
    {
        "name": "seats",
        "description": "Browse the 500 concert seats and check real-time availability.",
    },
    {
        "name": "reservations",
        "description": "High-concurrency temporary seat holds, payment confirmations, and cancellations.",
    },
    {
        "name": "bookings",
        "description": "Student booking history and active reservation queries.",
    },
]

app = FastAPI(
    title="College Concert Ticket API",
    description=(
        "High-concurrency ticket booking engine for 500 concert seats, engineered "
        "to handle 10,000+ simultaneous booking requests without race conditions, "
        "double-bookings, or overselling. Backed by atomic Supabase Postgres functions, "
        "row-level locking, and idempotent request deduplication."
    ),
    version="1.1.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


app.add_exception_handler(TicketingError, ticketing_error_handler)

app.include_router(health.router)
app.include_router(seats.router)
app.include_router(reservations.router)
app.include_router(bookings.router)
