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
    user_id: UUID = Field(
        ...,
        description="Unique identifier of the student making the reservation",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    seat_id: int = Field(
        ...,
        ge=1,
        le=500,
        description="Seat number to reserve (1-500)",
        examples=[17],
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Client-generated unique token to guarantee safe retries",
        examples=["order-checkout-001"],
    )


class PaymentRequest(BaseModel):
    user_id: UUID = Field(
        ...,
        description="Unique identifier of the student confirming the booking",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    outcome: PaymentOutcome = Field(
        ...,
        description="Simulated outcome: 'success', 'failure', or 'delayed'",
        examples=[PaymentOutcome.success],
    )
    delay_seconds: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Simulated processing delay in seconds when outcome is 'delayed'",
        examples=[3],
    )


class ReservationAction(BaseModel):
    user_id: UUID = Field(
        ...,
        description="Unique identifier of the student performing the cancellation",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )


class ReservationResponse(BaseModel):
    id: UUID = Field(
        ...,
        description="Unique UUID for this reservation record",
        examples=["123e4567-e89b-12d3-a456-426614174001"],
    )
    seat_id: int = Field(..., ge=1, le=500, description="Seat identifier", examples=[17])
    user_id: UUID = Field(
        ...,
        description="Student UUID who placed this reservation",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    idempotency_key: str = Field(
        ...,
        description="Idempotency key supplied with the reservation",
        examples=["order-checkout-001"],
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
