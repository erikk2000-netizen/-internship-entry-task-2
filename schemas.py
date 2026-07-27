from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator

class OperationCreate(BaseModel):
    operationId: str = Field(min_length=1, strip_whitespace=True)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    currency: str
    description: str | None = None

    @field_validator('currency')
    def check_currency(cls, value):
        if value != 'RUB':
            raise ValueError('Поддерживается валюта RUB')
        return value


class HealthStatus(BaseModel):
    status: str
    database: str


class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def check_date_range(self) -> "DateRange":
        if self.start > self.end:
            raise ValueError("Дата 'start' не может быть позже даты 'end'")
        return self
