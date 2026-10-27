# SeatLock API

A FastAPI backend for reserving and booking 500 concert seats.

## Hosted API

[https://seatlockig.onrender.com](https://seatlockig.onrender.com) ·
[API documentation](https://seatlockig.onrender.com/docs)

## Technology

- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL on Supabase
- **Database access:** Supabase RPC functions defined in [`supabase/schema.sql`](supabase/schema.sql)

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/health` | Health check |
| `GET` | `/favicon.ico` | Browser tab icon |
| `GET` | `/seats` | List seats and availability |
| `GET` | `/seats?available_only=true` | List available seats only |
| `POST` | `/reservations` | Hold a seat (`{"seat_id": 17, "user_id": 1}`) |
| `GET` | `/reservations/{reservation_id}` | Get reservation status |
| `POST` | `/reservations/{reservation_id}/confirm` | Confirm booking (`{"user_id": 1}`) |
| `POST` | `/reservations/{reservation_id}/cancel` | Cancel booking (`{"user_id": 1}`) |
| `GET` | `/users/{user_id}/bookings` | Get user's booking history |

Interactive API documentation is available at `/docs` when the server is
running. See the [API Guide](API_GUIDE.md) for setup instructions and example
requests for each endpoint.

## Run locally

1. Create a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql)
   in its SQL Editor.
2. From the project folder, create `.env` from `.env.example` and set your
   Supabase project URL and service-role key. Use the project URL without
   `/rest/v1`; keep the service-role key private and server-side.
3. In PowerShell, install dependencies and start the API:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env
   ```

Open [http://localhost:8000/docs](http://localhost:8000/docs) to try the
endpoints, or [http://localhost:8000/](http://localhost:8000/) for the health
check.

## Important details

- Seat holds last 300 seconds by default. Set `RESERVATION_HOLD_SECONDS` in
  `.env` to a value from 1 to 900.
- PostgreSQL transactions and seat row locks prevent two active bookings for
  the same seat. Reservation requests also support safe retries through an
  idempotency key.
- Payment is simulated; no real payment provider is connected.
- This demo accepts `user_id` in request data and does not authenticate users.
- Run automated tests with:

  ```powershell
  .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .\.venv\Scripts\python.exe -m pytest -q
  ```
