# College Concert Ticket API

A FastAPI backend for browsing and booking 500 concert seats. Supabase Postgres is the source of truth: database functions perform booking state changes atomically, and row locks prevent concurrent requests from booking the same seat.

> **Demo project:** payment outcomes are simulated, and request bodies supply `user_id` directly. This is not a production-ready payment or authentication system.

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Booking behavior](#booking-behavior)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Production considerations](#production-considerations)

## Features

- Lists all 500 seats and their current availability.
- Places temporary, configurable holds on seats.
- Confirms, cancels, or marks reservations as payment-failed.
- Provides reservation status and per-user booking history.
- Uses idempotency keys and database constraints to make booking retries safe.
- Exposes interactive OpenAPI documentation through FastAPI.

## Tech stack

- Python 3.12+
- FastAPI and Pydantic
- Supabase Postgres
- Pytest and HTTPX for API tests

## Getting started

### 1. Set up Supabase

Create a Supabase project. In its SQL Editor, run [`supabase/schema.sql`](supabase/schema.sql). The script creates the seat and reservation tables, seeds seats 1 through 500, and defines the Postgres functions used by the API.

### 2. Install dependencies

Create and activate a virtual environment, then install the application and test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi uvicorn supabase python-dotenv pytest httpx
```

If PowerShell prevents activation, use the Python executable in the environment directly (for example, `.venv\Scripts\python.exe -m pip ...`).

### 3. Configure environment variables

Copy the example file and fill in the Supabase project URL and service-role key:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
RESERVATION_HOLD_SECONDS=300
```

Use the project URL root, without `/rest/v1`. Keep the service-role key private and server-side; never put it in a browser application or commit it to source control.

`RESERVATION_HOLD_SECONDS` is optional, defaults to `300`, and must be between `1` and `900`.

### 4. Start the API

```powershell
uvicorn app.main:app --reload --env-file .env
```

The API is available at `http://localhost:8000`. Open `http://localhost:8000/docs` for Swagger UI or `http://localhost:8000/redoc` for ReDoc.

### Run with Docker

After creating `.env` as described above:

```powershell
docker build -t concert-tickets .
docker run --env-file .env -p 8000:8000 concert-tickets
```

## Configuration

| Variable | Required | Default | Description |
|---|---:|---:|---|
| `SUPABASE_URL` | Yes | — | Supabase project URL, without `/rest/v1` |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | — | Server-side key used by the API to call Supabase |
| `RESERVATION_HOLD_SECONDS` | No | `300` | Reservation hold duration in seconds (`1`–`900`) |

The health endpoint does not require a configured database. Database-backed endpoints return `503` if the Supabase settings are missing.

## API reference

All endpoints are served from the root path; interactive request and response schemas are available at `/docs`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Check that the API process is responding |
| `GET` | `/seats` | List seats and availability |
| `GET` | `/seats?available_only=true` | List only currently available seats |
| `POST` | `/reservations` | Reserve a seat |
| `GET` | `/reservations/{reservation_id}?user_id={uuid}` | Get a reservation's status |
| `POST` | `/reservations/{reservation_id}/confirm` | Simulate payment and confirm or fail a reservation |
| `POST` | `/reservations/{reservation_id}/cancel` | Cancel a reservation or booking |
| `GET` | `/users/{user_id}/bookings` | Get a user's booking history |

### Reserve a seat

Provide a UUID for `user_id`, a seat ID from 1 to 500, and a unique idempotency key for the user:

```powershell
curl.exe -X POST http://localhost:8000/reservations `
  -H "Content-Type: application/json" `
  -d '{"user_id":"123e4567-e89b-12d3-a456-426614174000","seat_id":17,"idempotency_key":"checkout-001"}'
```

The response includes the reservation `id`, its `reserved` status, and `expires_at`. Reusing the same key for the same user returns the original reservation.

### Simulate payment

Replace `RESERVATION_ID` with the `id` returned when reserving the seat. Set `outcome` to `success` or `failure`:

```powershell
curl.exe -X POST http://localhost:8000/reservations/RESERVATION_ID/confirm `
  -H "Content-Type: application/json" `
  -d '{"user_id":"123e4567-e89b-12d3-a456-426614174000","outcome":"success"}'
```

A successful outcome confirms the booking. A failed outcome releases the seat. To simulate a delayed successful payment, use `"outcome":"delayed"` and optionally set `delay_seconds` from 1 to 30 (default: 3):

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "outcome": "delayed",
  "delay_seconds": 8
}
```

The delayed outcome waits before attempting confirmation; it does not hold a database transaction open during the delay.

### Cancel a reservation

```powershell
curl.exe -X POST http://localhost:8000/reservations/RESERVATION_ID/cancel `
  -H "Content-Type: application/json" `
  -d '{"user_id":"123e4567-e89b-12d3-a456-426614174000"}'
```

## Booking behavior

- **Concurrent requests:** database functions lock the seat row during changes. A competing request for a seat that is already held or booked receives `409 seat_unavailable`.
- **Active-booking constraint:** a partial unique index prevents more than one reserved or confirmed booking per seat.
- **Expiring holds:** holds expire according to database time. Expired reservations no longer block a seat, and confirmation after expiry is rejected. No periodic expiry worker is required for correctness.
- **Idempotent retries:** `(user_id, idempotency_key)` is unique, and repeated reservation requests return the original reservation.
- **Safe repeated transitions:** repeating an already completed confirmation, payment failure, or cancellation does not apply the transition twice.
- **Reservation states:** `reserved`, `confirmed`, `cancelled`, `expired`, and `payment_failed`.

## Project structure

```text
app/
  core/        Settings, Supabase client, and application errors
  routers/     HTTP routes and dependency wiring
  schemas/     Request validation and response models
  services/    Seat, reservation, and booking-history operations
  main.py      FastAPI application assembly
supabase/
  schema.sql   Tables, indexes, seed data, and Postgres RPC functions
tests/
  test_api.py  API behavior tests using a fake Supabase client
load_test.py   Concurrent booking smoke test for a running API
Dockerfile     Container image definition
```

## Testing

Run the API tests:

```powershell
pytest -q
```

The tests use a fake Supabase client and do not require a live database.

To exercise the real concurrent-booking path, start the API with a configured Supabase project and run:

```powershell
python load_test.py --requests 100 --seat-id 500
```

Run the smoke test against an unused seat. It succeeds only if exactly one request reserves that seat and all other requests receive a conflict. The test reports the elapsed time and response counts; throughput depends on the Supabase plan, region, and network.

## Production considerations

This project is intended as a demo or starter. Before production use:

- Authenticate requests, validate Supabase JWTs, and derive the user ID from the verified identity rather than trusting request data.
- Replace simulated payment outcomes with a payment provider, persisted payment attempts, verified/idempotent webhooks, and reconciliation.
- Restrict service-role credentials to the backend; configure rate limiting, monitoring, structured logging, backups, and network controls.
- Use connection pooling and tune request limits for the Supabase plan. Keep external payment calls outside database transactions.
