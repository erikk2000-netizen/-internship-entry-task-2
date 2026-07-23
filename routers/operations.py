from fastapi import APIRouter, Request, Response, status

from schemas import OperationCreate
from services import create_operation_service, submit_operation_service, get_operation_data, get_operation_events_data

router = APIRouter(prefix="/operations", tags=["Operations"])

@router.post("")
def create_operation(operation_data: OperationCreate):
    return create_operation_service(operation_data)


@router.post("/{id}/submit")
async def submit_operation(id: str, request: Request):
    return submit_operation_service(id, request)


@router.get("/{id}")
def get_operation(id: str):
    return get_operation_data(id)


@router.get("/{id}/events")
def get_operation_events(id: str):
	return get_operation_events_data(id)
