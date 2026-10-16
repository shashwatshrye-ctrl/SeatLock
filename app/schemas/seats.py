from pydantic import BaseModel, Field


class SeatResponse(BaseModel):
    id: int = Field(..., ge=1, le=500, description="Seat identifier (1-500)", examples=[17])
    label: str = Field(..., description="Seat label", examples=["Seat 017"])
    available: bool = Field(..., description="Whether seat is currently available for reservation", examples=[True])
