
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI server with hot-reload
uvicorn app.main:app --reload --env-file .env --port 8000
```

Once started, the API will be live at:
- **Base URL:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`

*(If testing against the cloud deployment, you can use `https://seatlockig.onrender.com`)*.

---

## 2. API Endpoints Reference

All IDs (`user_id`, `seat_id`, `reservation_id`) use **standard decimal numbers (integers)**.

### Summary Table

| Method | Endpoint | Description | Sample Body |
|---|---|---|---|
| `GET` | `/health` | Server health status | _None_ |
| `GET` | `/seats` | Browse all 500 seats | _None_ |
| `GET` | `/seats?available_only=true` | Browse only available seats | _None_ |
| `POST` | `/reservations` | Place temporary hold on a seat | `{"seat_id": 17, "user_id": 1}` |
| `GET` | `/reservations/{id}` | Check status of a reservation | _None_ |
| `POST` | `/reservations/{id}/confirm` | Confirm payment & book seat | `{"user_id": 1}` |
| `POST` | `/reservations/{id}/cancel` | Cancel hold or confirmed booking | `{"user_id": 1}` |
| `GET` | `/users/{user_id}/bookings` | Get user's booking history | _None_ |

---

### Detailed Endpoint Specifications

#### 1. Health Check
* **`GET /health`**
* **Headers:** None
* **Response (`200 OK`):**
  ```json
  {
    "status": "ok"
  }
  ```

---

#### 2. List Seats & Availability
* **`GET /seats`** or **`GET /seats?available_only=true`**
* **Query Parameters:**
  - `available_only` *(boolean, optional, default: false)*: When `true`, returns only unreserved seats.
* **Response (`200 OK`):**
  ```json
  [
    {
      "id": 1,
      "label": "Seat 001",
      "available": true
    },
    {
      "id": 2,
      "label": "Seat 002",
      "available": false
    }
  ]
  ```

---

#### 3. Reserve a Seat (Temporary Hold)
* **`POST /reservations`**
* **Headers:** `Content-Type: application/json`
* **Request Body (Minimal & Uncluttered):**
  ```json
  {
    "seat_id": 17,
    "user_id": 1
  }
  ```
  *(Note: You can optionally pass `"idempotency_key": "custom-key"` if you want explicit idempotency control; otherwise the API auto-generates one).*

* **Response (`201 Created`):**
  ```json
  {
    "id": 1,
    "seat_id": 17,
    "user_id": 1,
    "idempotency_key": "auto-1-17-1730046522000",
    "status": "reserved",
    "created_at": "2026-10-27T16:30:00Z",
    "expires_at": "2026-10-27T16:35:00Z",
    "confirmed_at": null
  }
  ```
* **Conflict Response (`409 Conflict`):**
  If another user has already reserved or booked that seat:
  ```json
  {
    "detail": "seat_unavailable"
  }
  ```

---

#### 4. Get Reservation Status
* **`GET /reservations/{reservation_id}`**
* **Example:** `GET /reservations/1`
* **Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "seat_id": 17,
    "user_id": 1,
    "idempotency_key": "auto-1-17-1730046522000",
    "status": "reserved",
    "created_at": "2026-10-27T16:30:00Z",
    "expires_at": "2026-10-27T16:35:00Z",
    "confirmed_at": null
  }
  ```
  *(If the 300-second window passes without confirmation, the returned `status` will automatically change to `"expired"`).*

---

#### 5. Confirm Reservation (Simulate Payment)
* **`POST /reservations/{reservation_id}/confirm`**
* **Example:** `POST /reservations/1/confirm`
* **Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "user_id": 1
  }
  ```
  *(Optional fields: `"outcome": "success"` (default) or `"failure"`, `"delay_seconds": 0`).*

* **Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "seat_id": 17,
    "user_id": 1,
    "idempotency_key": "auto-1-17-1730046522000",
    "status": "confirmed",
    "created_at": "2026-10-27T16:30:00Z",
    "expires_at": null,
    "confirmed_at": "2026-10-27T16:31:12Z"
  }
  ```

---

#### 6. Cancel Reservation or Booking
* **`POST /reservations/{reservation_id}/cancel`**
* **Example:** `POST /reservations/1/cancel`
* **Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "user_id": 1
  }
  ```
* **Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "seat_id": 17,
    "user_id": 1,
    "idempotency_key": "auto-1-17-1730046522000",
    "status": "cancelled",
    "created_at": "2026-10-27T16:30:00Z",
    "expires_at": null,
    "confirmed_at": null
  }
  ```

---

#### 7. View User Booking History
* **`GET /users/{user_id}/bookings`**
* **Example:** `GET /users/1/bookings`
* **Response (`200 OK`):**
  ```json
  [
    {
      "id": 1,
      "seat_id": 17,
      "user_id": 1,
      "status": "confirmed",
      "created_at": "2026-10-27T16:30:00Z",
      "expires_at": null,
      "confirmed_at": "2026-10-27T16:31:12Z"
    }
  ]
  ```

---

## 3. Step-by-Step Testing Using Postman

### Step A: Configure Postman Environment
1. Open Postman.
2. In the top right, create an Environment or a Collection Variable named `base_url`.
3. Set the initial and current value to:
   ```
   http://localhost:8000
   ```
   *(Or `https://seatlockig.onrender.com` if using the live hosted instance).*

---

### Step B: The Standard End-to-End Test Workflow

#### Request 1: Health Check
- **Method:** `GET`
- **URL:** `{{base_url}}/health`
- **Click Send** $\rightarrow$ Should return status `200 OK` with `{"status": "ok"}`.

#### Request 2: Check Available Seats
- **Method:** `GET`
- **URL:** `{{base_url}}/seats?available_only=true`
- **Click Send** $\rightarrow$ Returns a list of seats that are currently open. Pick any seat number (e.g. `17`).

#### Request 3: Reserve Seat #17 for User #1
- **Method:** `POST`
- **URL:** `{{base_url}}/reservations`
- **Headers:** `Content-Type: application/json`
- **Body** $\rightarrow$ Select **raw** $\rightarrow$ **JSON**:
  ```json
  {
    "seat_id": 17,
    "user_id": 1
  }
  ```
- **Click Send** $\rightarrow$ Returns `201 Created` with `"status": "reserved"` and a numeric `"id": 1`.

#### Request 4: Test Concurrency Conflict (Simulating Double Booking)
- **Method:** `POST`
- **URL:** `{{base_url}}/reservations`
- **Body:**
  ```json
  {
    "seat_id": 17,
    "user_id": 2
  }
  ```
- **Click Send** $\rightarrow$ Returns **`409 Conflict`** with:
  ```json
  {
    "detail": "seat_unavailable"
  }
  ```
  *(Proves the row-level lock successfully prevented User #2 from stealing User #1's seat!)*

#### Request 5: Check Status of Reservation #1
- **Method:** `GET`
- **URL:** `{{base_url}}/reservations/1`
- **Click Send** $\rightarrow$ Returns `200 OK` with `"status": "reserved"`.

#### Request 6: Confirm Booking (Simulate Payment)
- **Method:** `POST`
- **URL:** `{{base_url}}/reservations/1/confirm`
- **Headers:** `Content-Type: application/json`
- **Body:**
  ```json
  {
    "user_id": 1
  }
  ```
- **Click Send** $\rightarrow$ Returns `200 OK` with `"status": "confirmed"` and a timestamp for `confirmed_at`.

#### Request 7: Verify History for User #1
- **Method:** `GET`
- **URL:** `{{base_url}}/users/1/bookings`
- **Click Send** $\rightarrow$ Returns an array containing the confirmed booking for seat 17.

---

## 4. Postman Collection JSON (One-Click Import)

You can import this entire pre-configured collection directly into Postman:

1. In Postman, click **Import** (top left).
2. Choose **Raw text**.
3. Paste the following JSON block and click **Import**:

```json
{
  "info": {
    "name": "SeatLock Concert API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    }
  ],
  "item": [
    {
      "name": "1. Health Check",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/health"
      }
    },
    {
      "name": "2. List Available Seats",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/seats?available_only=true"
      }
    },
    {
      "name": "3. Reserve Seat",
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"seat_id\": 17,\n  \"user_id\": 1\n}"
        },
        "url": "{{base_url}}/reservations"
      }
    },
    {
      "name": "4. Get Reservation Status",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/reservations/1"
      }
    },
    {
      "name": "5. Confirm Booking (Payment)",
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"user_id\": 1\n}"
        },
        "url": "{{base_url}}/reservations/1/confirm"
      }
    },
    {
      "name": "6. Cancel Reservation / Booking",
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"user_id\": 1\n}"
        },
        "url": "{{base_url}}/reservations/1/cancel"
      }
    },
    {
      "name": "7. User Booking History",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/users/1/bookings"
      }
    }
  ]
}
```

---

## 5. Automated Tests

You can also run the complete automated test suite locally at any time:

```powershell
# Run the 18 Pytest unit and integration tests
.\.venv\Scripts\pytest -v

# Run the 100-user concurrent race-condition benchmark
python load_test.py --base-url http://localhost:8000 --requests 100 --seat-id 50
```
