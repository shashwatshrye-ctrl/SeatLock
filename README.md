# College Concert Ticket Booking Platform (SeatLock API)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-14%20Passed-brightgreen.svg)]()

A high-concurrency ticket booking engine designed for 500 concert seats during flash-sale conditions where 10,000 students attempt to book simultaneously at 6:00 PM. Built on **FastAPI** and **PostgreSQL (Supabase)**, the platform guarantees **zero double-bookings**, **idempotent retries**, **lazy and automated hold expirations**, and **simulated payment lifecycles**.

---

## Table of Contents
1. [System Architecture & Concurrency Model](#system-architecture--concurrency-model)
2. [Entity Relationship Diagram (ERD)](#entity-relationship-diagram-erd)
3. [Booking State Machine & Workflow Diagrams](#booking-state-machine--workflow-diagrams)
4. [Expected Functionality Implementation](#expected-functionality-implementation)
5. [Quickstart & Deployment](#quickstart--deployment)
6. [Docker Deployment](#docker-deployment)
7. [API Documentation & Examples](#api-documentation--examples)
8. [Concurrency Handling & Scaling Strategy](#concurrency-handling--scaling-strategy)
9. [Load Testing & Benchmark Results](#load-testing--benchmark-results)
10. [Test Suite](#test-suite)

---

## System Architecture & Concurrency Model

When 10,000 students rush to reserve 500 seats at the same second:
1. **Network Layer:** FastAPI handles high-throughput asynchronous I/O and passes requests to PostgreSQL.
2. **Idempotency Gate:** An advisory lock hashed on `(user_id, idempotency_key)` serializes identical requests from the same user, preventing double-clicks or repeated network packets.
3. **Seat Lock Serialization:** A Postgres row-level lock (`SELECT ... FROM seats WHERE id = p_seat_id FOR UPDATE`) serializes all simultaneous requests competing for that particular seat.
4. **Hold Expiry Evaluation:** The database atomically sweeps any expired holds on the seat before evaluating availability using `clock_timestamp()`.
5. **Conflict Rejection:** If the seat is actively held or confirmed, competing requests immediately receive `409 Conflict (seat_unavailable)` without deadlock.
6. **Unique Constraint Safeguard:** A partial unique index (`one_live_booking_per_seat`) enforces at the physical storage engine level that no more than one active reservation can exist per seat.

```mermaid
flowchart TD
    A[Student Client / Web Portal] -->|POST /reservations| B[FastAPI Gateway]
    B -->|RPC reserve_seat| C[PostgreSQL Transaction]
    
    subgraph PostgreSQL Atomic RPC
        C --> D{Acquire Advisory Lock<br>user_id + idempotency_key}
        D -->|Duplicate Key| E[Return Existing Reservation]
        D -->|New Key| F[Lock Seat Row: SELECT FOR UPDATE]
        F --> G[Lazy-expire lapsed holds on seat]
        G --> H{Is seat held or confirmed?}
        H -->|Yes| I[Rollback & Return 409 Conflict]
        H -->|No| J[Insert new reservation with expires_at]
    end
    
    J --> K[Return 201 Created]
    I --> B
    K --> B
    E --> B
```

---

## Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    SEATS ||--o{ RESERVATIONS : "has"
    
    SEATS {
        int id PK "1 to 500, CHECK (id BETWEEN 1 AND 500)"
        text label "Display name (e.g. 'Seat 017'), UNIQUE"
    }
    
    RESERVATIONS {
        uuid id PK "gen_random_uuid()"
        int seat_id FK "REFERENCES seats(id)"
        uuid user_id "Student UUID"
        text idempotency_key "Client token, UNIQUE(user_id, idempotency_key)"
        text status "reserved | confirmed | cancelled | expired | payment_failed"
        timestamptz created_at "now()"
        timestamptz expires_at "Hold expiration deadline"
        timestamptz confirmed_at "Payment confirmation timestamp"
    }
```

### Key Constraints & Indexes
- **`seats.id`**: Primary key constrained between 1 and 500. Pre-seeded with 500 seats.
- **`one_live_booking_per_seat`**: Partial unique index on `reservations(seat_id) WHERE status IN ('reserved', 'confirmed')`. Prevents race conditions at the database level.
- **`reservations_by_user`**: Composite index on `(user_id, created_at DESC)` for sub-millisecond booking history lookups.
- **`idx_reservations_active_expires`**: Partial index on `(expires_at) WHERE status = 'reserved'` for $O(\log n)$ expiration resolution.

---

## Booking State Machine & Workflow Diagrams

```mermaid
stateDiagram-v2
    [*] --> reserved: reserve_seat() [Holds for 300s]
    
    reserved --> confirmed: confirm_reservation() [Payment Success]
    reserved --> payment_failed: fail_payment() [Payment Failure]
    reserved --> expired: Timer lapsed (expires_at <= now())
    reserved --> cancelled: cancel_reservation() [User Cancel]
    
    confirmed --> cancelled: cancel_reservation() [Booking Cancel]
    
    payment_failed --> [*]: Seat Released
    expired --> [*]: Seat Released
    cancelled --> [*]: Seat Released
    confirmed --> [*]: Ticket Issued
```

### Complete Booking Workflow
```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL
    participant Gateway as Payment Gateway (Simulated)

    Student->>API: GET /seats?available_only=true
    API->>DB: RPC list_seats(true)
    DB-->>API: List of available seats
    API-->>Student: 200 OK [Seat 17 available]

    Student->>API: POST /reservations (Seat 17, Idempotency-Key)
    API->>DB: RPC reserve_seat(p_seat_id=17)
    Note over DB: Lock Seat 17 FOR UPDATE<br/>Insert reservation (status='reserved')
    DB-->>API: Reservation Created (expires in 300s)
    API-->>Student: 201 Created (reservation_id, expires_at)

    alt Payment Success (within hold window)
        Student->>API: POST /reservations/{id}/confirm (outcome='success')
        API->>Gateway: Process transaction
        Gateway-->>API: Success
        API->>DB: RPC confirm_reservation()
        Note over DB: Status -> 'confirmed', expires_at = NULL
        DB-->>API: Confirmed
        API-->>Student: 200 OK (status: 'confirmed')
    else Payment Failure / Abandoned
        Student->>API: POST /reservations/{id}/confirm (outcome='failure')
        API->>DB: RPC fail_payment()
        Note over DB: Status -> 'payment_failed', seat immediately freed
        DB-->>API: Released
        API-->>Student: 200 OK (status: 'payment_failed')
    else Hold Expired
        Note over Student, DB: User took > 300 seconds
        Student->>API: POST /reservations/{id}/confirm (outcome='success')
        API->>DB: RPC confirm_reservation()
        Note over DB: Check expires_at <= clock_timestamp()<br/>Status -> 'expired'
        DB-->>API: Error: reservation_expired
        API-->>Student: 410 Gone (detail: 'reservation_expired')
    end
```

---

## Expected Functionality Implementation

| Requirement | Implementation Detail | Status |
|---|---|:---:|
| **01 View seats, reserve, & confirm** | `/seats`, `POST /reservations`, `POST /reservations/{id}/confirm` | Complete |
| **02 Prevent duplicate seat booking** | Row-level locks (`SELECT FOR UPDATE`) + partial unique index `one_live_booking_per_seat` | Complete |
| **03 Temporary expiring reservations** | Configurable `RESERVATION_HOLD_SECONDS` (1–900s) + atomic lazy & bulk expiration | Complete |
| **04 Cancellations & reallocation** | `POST /reservations/{id}/cancel` immediately transitions status to `cancelled` and frees seat | Complete |
| **05 Simulated payment processing** | Supports `success`, `failure`, and `delayed` (with configurable `delay_seconds`) | Complete |
| **06 Concurrency & idempotency** | `pg_advisory_xact_lock` + `UNIQUE(user_id, idempotency_key)` protects repeated requests | Complete |
| **07 History & reservation status** | `GET /reservations/{id}` and `GET /users/{user_id}/bookings` | Complete |

---

## Quickstart & Deployment

### Prerequisites
- Python 3.12+
- Supabase Account or self-hosted PostgreSQL 15+

### 1. Database Setup
1. Log in to your Supabase project dashboard.
2. Open the **SQL Editor**.
3. Paste and run the entire contents of [`supabase/schema.sql`](supabase/schema.sql).
4. The script seeds seats 1–500, sets up tables, indexes, RPC functions, and Row-Level Security (RLS).

### 2. Local Environment Setup
```powershell
# Clone and enter workspace
cd d:\Projects\e

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install production and development dependencies
python -m pip install -r requirements-dev.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Populate `.env`:
```ini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
RESERVATION_HOLD_SECONDS=300
```

### 4. Run Development Server
```powershell
uvicorn app.main:app --reload --env-file .env
```
Visit:
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Interactive ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## Docker Deployment

### Run with Docker Compose (Recommended)
```powershell
docker compose up --build -d
```

### Run with Docker CLI
```powershell
# Build container
docker build -t concert-tickets .

# Run container with environment configuration
docker run -d --name concert-ticket-api --env-file .env -p 8000:8000 concert-tickets
```

---

## API Documentation & Examples

### 1. List Available Seats
```powershell
curl.exe -X GET "http://localhost:8000/seats?available_only=true"
```
**Response (200 OK):**
```json
[
  {"id": 1, "label": "Seat 001", "available": true},
  {"id": 2, "label": "Seat 002", "available": true}
]
```

### 2. Reserve a Seat (Atomic Hold)
```powershell
curl.exe -X POST "http://localhost:8000/reservations" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "seat_id": 17,
    "idempotency_key": "checkout-order-001"
  }'
```
**Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174001",
  "seat_id": 17,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "idempotency_key": "checkout-order-001",
  "status": "reserved",
  "created_at": "2026-10-16T15:30:00Z",
  "expires_at": "2026-10-16T15:35:00Z",
  "confirmed_at": null
}
```

### 3. Check Reservation Status
```powershell
curl.exe -X GET "http://localhost:8000/reservations/123e4567-e89b-12d3-a456-426614174001?user_id=123e4567-e89b-12d3-a456-426614174000"
```

### 4. Confirm Reservation (Successful Payment)
```powershell
curl.exe -X POST "http://localhost:8000/reservations/123e4567-e89b-12d3-a456-426614174001/confirm" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "outcome": "success"
  }'
```
**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174001",
  "seat_id": 17,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "idempotency_key": "checkout-order-001",
  "status": "confirmed",
  "created_at": "2026-10-16T15:30:00Z",
  "expires_at": null,
  "confirmed_at": "2026-10-16T15:31:12Z"
}
```

### 5. Simulate Failed Payment (Releases Seat)
```powershell
curl.exe -X POST "http://localhost:8000/reservations/123e4567-e89b-12d3-a456-426614174001/confirm" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "outcome": "failure"
  }'
```

### 6. Simulate Delayed Payment
```powershell
curl.exe -X POST "http://localhost:8000/reservations/123e4567-e89b-12d3-a456-426614174001/confirm" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "outcome": "delayed",
    "delay_seconds": 5
  }'
```

### 7. Cancel a Reservation or Booking
```powershell
curl.exe -X POST "http://localhost:8000/reservations/123e4567-e89b-12d3-a456-426614174001/cancel" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

### 8. View Student Booking History
```powershell
curl.exe -X GET "http://localhost:8000/users/123e4567-e89b-12d3-a456-426614174000/bookings"
```

---

## Concurrency Handling & Scaling Strategy

### How Concurrency Is Handled Under High Contention

1. **Row-Level Serialization (`SELECT ... FOR UPDATE`):**
   - Locking is scoped strictly to the requested seat row (`public.seats.id`).
   - Two users requesting **different seats** (e.g. Seat 10 and Seat 11) do **not** block each other. They execute in parallel without lock contention.
   - Competing requests for the **same seat** are serialized by Postgres. The first transaction places the hold; subsequent transactions instantly read the updated state and return `409 seat_unavailable`.

2. **Deadlock Prevention:**
   - All write functions (`reserve_seat`, `confirm_reservation`, `fail_payment`, `cancel_reservation`) follow a deterministic locking order:
     1. Seat row lock (`public.seats`)
     2. Reservation row lock (`public.reservations`)
   - Strict hierarchical locking eliminates cross-resource circular wait deadlocks.

3. **Non-Blocking Payment Processing:**
   - External payment delays (simulated via `asyncio.sleep` or real payment providers) occur **outside** of the database transaction. Database locks are never held open across network calls to payment gateways.
   - Synchronous Supabase RPC calls are offloaded to Python thread workers via `asyncio.to_thread`, keeping FastAPI's `asyncio` event loop responsive to 10,000+ concurrent connections.

4. **Guaranteed Exact-Once Idempotency:**
   - Advisory transaction locks hashed on `user_id || ':' || idempotency_key` prevent duplicate reservations if a user double-taps the booking button or if retries occur over unstable mobile connections.

### Horizontal Scaling Roadmap (10,000+ Concurrent Students)

To scale from a single server to handle massive surges:
```mermaid
graph LR
    Students[10,000 Students] --> CDN[Cloudflare CDN / Edge Cache]
    CDN --> LB[Application Load Balancer]
    LB --> Node1[FastAPI Container 1]
    LB --> Node2[FastAPI Container 2]
    LB --> Node3[FastAPI Container N]
    
    Node1 & Node2 & Node3 --> Pooler[PgBouncer / Supavisor Connection Pooler]
    Pooler --> Primary[(Postgres Primary: All Writes)]
    Node1 & Node2 & Node3 -.-> Redis[(Redis Cache: Seat Availability)]
```

1. **Stateless FastAPI Containers:** Application instances contain no local state. They scale horizontally across Kubernetes pods or ECS tasks behind an AWS ALB or Google Cloud Load Balancer.
2. **Connection Pooling (PgBouncer / Supavisor):** Prevents Postgres connection exhaustion when thousands of app workers query the database simultaneously using transaction-mode pooling.
3. **Redis Read Cache for Seat Availability:** 90% of traffic during ticket drop is read traffic (refreshing the seating chart). Caching `/seats` in Redis with a 1-second TTL or invalidation on reservation events offloads 95%+ of query pressure from Postgres.
4. **Virtual Waiting Room (Queue):** During extreme surges, fronting the booking route with a token bucket queue (e.g. AWS SQS or Cloudflare Waiting Room) meters traffic into the database at its peak processing capacity.

---

## Load Testing & Benchmark Results

The repository includes a concurrent load-testing tool (`load_test.py`) that bombards a single seat with simultaneous requests to verify that row-level locks strictly prevent double-bookings.

### Running the Load Test
```powershell
python load_test.py --base-url http://localhost:8000 --requests 100 --seat-id 500 --concurrency 50
```

### Benchmark Results (100 Simultaneous Competitors on Seat #500)
```text
======================================================================
RACE CONDITION TEST: 100 users competing for Seat #500
======================================================================

[Results]
Total Requests:       100
Concurrency Level:    50
Elapsed Time:         0.842 s
Throughput:           118.8 req/s
Successful Holds:     1 (Expected: exactly 1)
Seat Conflicts (409): 99 (Expected: 99)
Unexpected Errors:    0
Latency min / avg:    18.40 ms / 41.25 ms
Latency p50 / p95:    38.10 ms / 65.40 ms
Latency p99 / max:    78.20 ms / 89.15 ms

>>> TEST PASSED: Row-level lock strictly prevented double-booking!
```

---

## Test Suite

The test suite tests the API endpoints, error handling, lifecycle transitions, delayed confirmations, and edge cases.

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### Test Coverage Summary
- `test_reserve_sends_request_to_database`: Verifies reservation creation and default hold duration.
- `test_unavailable_seat_maps_to_conflict`: Confirms `409 seat_unavailable` error mapping.
- `test_get_reservation_status`: Verifies status retrieval.
- `test_get_reservation_not_found`: Confirms `404 reservation_not_found`.
- `test_confirmation_endpoint_accepts_successful_payment`: Tests payment confirmation lifecycle.
- `test_failed_payment_releases_reservation`: Tests immediate seat release upon payment failure.
- `test_delayed_payment_confirmation`: Tests simulated delayed transactions.
- `test_cancel_reservation`: Tests voluntary user cancellations.
- `test_list_seats`: Verifies 500 seat catalog generation.
- `test_list_seats_available_only`: Tests availability filtering.
- `test_booking_history`: Tests student history retrieval.
- `test_health_does_not_require_database`: Confirms standalone liveness check.
- `test_validation_error_invalid_seat_number`: Tests boundary validation (seat > 500).
- `test_database_not_configured_returns_503`: Tests graceful 503 handling when credentials are missing.
