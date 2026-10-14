from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentOutcome(str, Enum):
    success = "success"
    failure = "failure"
    delayed = "delayed"


class ReservationStatus(str, Enum):
    reserved = "reserved"
    confirmed = "confirmed"
    cancelled = "cancelled"
    expired = "expired"
    payment_failed = "payment_failed"


class ReservationCreate(BaseModel):
    user_id: UUID
    seat_id: int = Field(ge=1, le=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class PaymentRequest(BaseModel):
    user_id: UUID
    outcome: PaymentOutcome
    delay_seconds: int = Field(default=3, ge=1, le=30)


class ReservationAction(BaseModel):
    user_id: UUID


class ReservationResponse(BaseModel):
    id: UUID
    seat_id: int
    user_id: UUID
    idempotency_key: str
    status: ReservationStatus
    created_at: datetime
    expires_at: datetime | None = None
    confirmed_at: datetime | None = None
