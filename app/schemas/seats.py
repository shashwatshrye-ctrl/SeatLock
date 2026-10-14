from pydantic import BaseModel


class SeatResponse(BaseModel):
    id: int
    label: str
    available: bool
