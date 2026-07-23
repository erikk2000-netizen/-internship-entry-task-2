from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

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


