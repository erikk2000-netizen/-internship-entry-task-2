import os
import pytest
import httpx
from sqlalchemy import text

from database import engine

# Берем адрес из переменных окружения.
# Если переменной нет (например, тесты запускают локально без Docker),
# используем запасной вариант для локальной разработки.
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
OPERATION_COUNT = os.getenv("OPERATION_COUNT", "0")


@pytest.fixture
def client():
    # httpx делает реальные сетевые запросы по указанному адресу
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        yield client


def test_concurrent():
    try:
        operation_count = int(OPERATION_COUNT)
    except ValueError:
        operation_count = 0

    if  operation_count == 0:
        return

    container_id = 'test'

    with engine.begin() as connection:
        row = connection.execute(text(f"SELECT operationId FROM operations WHERE operationId LIKE '%-{container_id}' ORDER BY operationId DESC LIMIT 0,1")).mappings().one_or_none()

    if row is None:
        start_id = 1
    else:
        start_id = int(row['operationId'].split('-')[0]) + 1

    end_id = start_id + operation_count

    payload = {
        "amount": "10.00",
        "currency": "RUB"
    }

    for id in range(start_id, end_id):
        payload['operationId'] = str(id) + '-' + container_id
        httpx.post(BASE_URL + '/operations', json=payload)

    for id in range(start_id, end_id):
        httpx.post(BASE_URL + '/operations/' + str(id) + '-' + container_id + '/submit')

    with engine.begin() as connection:
        row = connection.execute(text(f"SELECT COUNT(providerPaymentId) AS cnt FROM receipts WHERE (operationId BETWEEN '{start_id}-{container_id}' AND '{end_id}-{container_id}') AND isIgnored = 0 GROUP BY operationId ORDER BY cnt DESC LIMIT 0,1")).mappings().one_or_none()
        assert row is None or row['cnt'] == 1, (
            "Detected multiple non-ignored receipts for one operation.\n"
            f"Required: 1 | Actual: {row['cnt']}"
        )

        row = connection.execute(text(f"SELECT COUNT(id) AS cnt FROM events WHERE (operationId BETWEEN '{start_id}-{container_id}' AND '{end_id}-{container_id}') GROUP BY toStatus, operationId ORDER BY cnt DESC LIMIT 0,1")).mappings().one_or_none()
        assert row is None or row['cnt'] == 1, (
            "Detected multiple events for one operation status change.\n"
            f"Required: 1 | Actual: {row['cnt']}"
        )
