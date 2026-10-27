from datetime import datetime
from enum import Enum

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
    seat_id: int = Field(
        ...,
        ge=1,
        le=500,
        description="Seat number to reserve (1-500)",
        examples=[17],
    )
    user_id: int = Field(
        ...,
        ge=1,
        description="Numeric student/user ID",
        examples=[1],
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional unique key to guarantee safe retries (auto-generated if omitted)",
        examples=["req-001"],
    )


class PaymentRequest(BaseModel):
    user_id: int = Field(
        ...,
        ge=1,
        description="Numeric student/user ID confirming the booking",
        examples=[1],
    )
    outcome: PaymentOutcome = Field(
        default=PaymentOutcome.success,
        description="Payment outcome ('success', 'failure', or 'delayed')",
        examples=[PaymentOutcome.success],
    )
    delay_seconds: int = Field(
        default=0,
        ge=0,
        le=30,
        description="Simulated processing delay in seconds when outcome is 'delayed'",
        examples=[0],
    )


class ReservationAction(BaseModel):
    user_id: int = Field(
        ...,
        ge=1,
        description="Numeric student/user ID",
        examples=[1],
    )


class ReservationResponse(BaseModel):
    id: int = Field(
        ...,
        description="Numeric reservation ID",
        examples=[1],
    )
    seat_id: int = Field(..., ge=1, le=500, description="Seat identifier", examples=[17])
    user_id: int = Field(
        ...,
        ge=1,
        description="Numeric user ID who placed this reservation",
        examples=[1],
    )
    idempotency_key: str = Field(
        ...,
        description="Idempotency key supplied with the reservation",
        examples=["req-001"],
    )
    status: ReservationStatus = Field(
        ...,
        description="Current reservation lifecycle status",
        examples=[ReservationStatus.reserved],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when reservation was created",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the temporary reservation expires (if still reserved)",
    )
    confirmed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when booking was successfully paid and confirmed",
    )
