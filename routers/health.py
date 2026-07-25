from sqlalchemy import text
from fastapi import APIRouter, status

from database import engine
from schemas import HealthStatus

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", status_code=status.HTTP_200_OK, response_model=HealthStatus, tags=["Monitoring"])
def health():
    health = {"status": "healthy", "database": "healthy"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT VERSION()"))
    except Exception:
        health["database"] = "unhealthy"
        health["status"] = "unhealthy"

    if health["status"] != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health
        )

    return health
