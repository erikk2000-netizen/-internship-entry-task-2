from fastapi import APIRouter, Depends

from schemas import DateRange
from services import basic_metrics_service, date_to_timestamp

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/basic")
async def get_basic_metrics(dates: DateRange = Depends()):
    data_dict = dates.model_dump()

    return basic_metrics_service(date_to_timestamp(data_dict["start"]), date_to_timestamp(data_dict["end"]))
