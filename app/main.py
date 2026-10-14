from fastapi import FastAPI

from app.core.errors import TicketingError, ticketing_error_handler
from app.routers import bookings, health, reservations, seats

app = FastAPI(
    title="College Concert Ticket API",
    description="A ticket-booking API backed by atomic Supabase Postgres functions.",
    version="1.1.0",
)
app.add_exception_handler(TicketingError, ticketing_error_handler)

app.include_router(health.router)
app.include_router(seats.router)
app.include_router(reservations.router)
app.include_router(bookings.router)
