from fastapi import APIRouter
from app.schemas.health import HealthStatus

router = APIRouter(tags=["health"])

@router.get("/health", response_model=HealthStatus, summary="Health check")
async def health() -> HealthStatus:
    return HealthStatus(status="ok")
