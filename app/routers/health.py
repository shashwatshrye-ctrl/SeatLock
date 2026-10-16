from fastapi import APIRouter, status

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Liveness check endpoint. Does not require database connection.",
    responses={
        status.HTTP_200_OK: {"description": "Service is live and responding."},
    },
)
@router.get(
    "/",
    response_model=HealthResponse,
    summary="Root health check",
    description="Root endpoint for a simple liveness check.",
    include_in_schema=False,
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
