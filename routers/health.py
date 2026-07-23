from sqlalchemy import text
from fastapi import APIRouter, Response, status

from database import engine

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
def test_db():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT VERSION()"))

        return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

