from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Machine-readable error code", examples=["seat_unavailable"])
