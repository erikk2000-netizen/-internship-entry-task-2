from fastapi import APIRouter

from services import finalize_operation_service

router = APIRouter(prefix="/receipts", tags=["Receipts"])

@router.post("")
async def finalize_operation(receipt_data: dict[str, str]):
    return finalize_operation_service(receipt_data)
