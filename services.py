import json
import time
import random
import datetime
import requests
from sqlalchemy import text, exc
from fastapi import Request, Response, status

from database import engine
from config import PROVIDER_PAYMENTS_URL, STATUS_CREATED, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_REJECTED, BACKOFF_LIMIT, BACKOFF_SECONDS, BACKOFF_JITTER_SECONDS, operation_statuses

def operation_submit_service(operation_id: str):
    with engine.begin() as connection:
        result = connection.execute(text(f"UPDATE operations SET isLockedForSubmit = 1 WHERE isLockedForSubmit = 0 AND status = {STATUS_PROCESSING} AND operationId = :operationId"), {'operationId': operation_id})

    if result.rowcount != 1:
        return

    with engine.begin() as connection:
        query = text("SELECT amount, currency FROM operations WHERE operationId = :operationId")
        row = connection.execute(query, {'operationId': operation_id}).mappings().one_or_none()

    if row is None:
        return

    headers = {
        'Content-Type': 'application/json',
        'Idempotency-Key': operation_id,
        'X-Correlation-ID': operation_id
    }

    data = json.dumps({
        'operationId': operation_id,
        'amount': format_amount(row['amount']),
        'currency': row['currency']
    })

    attempts_count = 0

    while True:
        attempts_count += 1

        if attempts_count > BACKOFF_LIMIT:
            unlock_operation(operation_id)
            break

        query = text("INSERT INTO submits (operationId, occurredAt) VALUES (:operationId, :occurredAt)")
        sql_values = {
            'operationId': operation_id,
            'occurredAt': int(time.time())
        }
        response_values = {
            'responseTimeMilliseconds': 0,
            'responseStatusCode': None,
            'providerPaymentId': None,
            'status': None,
            'isRegularResponse': 0,
            'exception': None
        }
        submit_id = None
        start_on = time.time()

        try:
            with engine.begin() as connection:
                result = connection.execute(query, sql_values)

            submit_id = result.lastrowid
            # Отправка POST-запроса
            response = requests.post(PROVIDER_PAYMENTS_URL, headers=headers, data=data, timeout=10)
            response_values['responseStatusCode'] = response.status_code

            if response.status_code != status.HTTP_202_ACCEPTED:
                raise requests.exceptions.RequestException("The external API connection failed.")

            # Проверка, вернул ли сервер JSON и парсинг в словарь Python
            response_data = response.json()

            if 'providerPaymentId' in response_data:
                response_values['providerPaymentId'] = response_data['providerPaymentId']

            if 'status' in response_data:
                response_values['status'] = response_data['status']

            if (
                response_values['status'] is None
                or not isinstance(response_values['providerPaymentId'], str)
                or not response_values['providerPaymentId']
            ):
                raise requests.exceptions.RequestException("Missing external API requested data.")

            response_values['isRegularResponse'] = 1
        except Exception as e:
            response_values['exception'] = str(e)
        finally:
            response_values['responseTimeMilliseconds'] = int((time.time() - start_on) * 1000)

        with engine.begin() as connection:
            if submit_id is not None:
                query = text(f"UPDATE submits SET responseTimeMilliseconds = :responseTimeMilliseconds, responseStatusCode = :responseStatusCode, providerPaymentId = :providerPaymentId, status = :status, isRegularResponse = :isRegularResponse, exception = :exception WHERE id = {submit_id}")
                connection.execute(query, response_values)

            if response_values['isRegularResponse'] == 1:
                response_values['operationId'] = operation_id
                query = text("UPDATE operations SET providerPaymentId = COALESCE(providerPaymentId, :providerPaymentId) WHERE operationId = :operationId")
                connection.execute(query, response_values)

        if response_values['isRegularResponse'] == 0:
            time.sleep(BACKOFF_SECONDS + random.random() * BACKOFF_JITTER_SECONDS)
        else:
            unlock_operation(operation_id)
            break


def get_operation_data(id: str):
    query = text("SELECT * FROM operations WHERE operationId = :id")
    param_dict = {"id": id}

    with engine.begin() as connection:
        row = connection.execute(query, param_dict).mappings().one_or_none()

        if row:
            data_dict = dict(row)
            data_dict['status'] = format_status(data_dict['status'])
            data_dict["amount"] = format_amount(data_dict["amount"])

            return data_dict

        return Response(status_code=status.HTTP_404_NOT_FOUND)


def get_operation_events_data(id: str):
    query = text("SELECT * FROM events WHERE operationId = :id ORDER BY id ASC")
    param_dict = {"id": id}

    try:
        with engine.begin() as connection:
            result = connection.execute(query, param_dict)
    except Exception as e:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    output = []

    for row in result:
        data_dict = {
            'eventId': row.id,
            'type': format_status(row.type),
            'fromStatus': format_status(row.fromStatus),
            'toStatus': format_status(row.toStatus),
            'message': row.message,
            'occurredAt': datetime.datetime.fromtimestamp(row.occurredAt, tz=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        }

        output.append(data_dict)

    if len(output) > 0:
        return output

    return Response(status_code=status.HTTP_404_NOT_FOUND)


def format_status(status):
    if status is None:
        return None

    return operation_statuses[status]


def format_amount(amount):
    return f"{amount:.2f}"


def create_operation_service(data_dict: dict):
    try:
        query = text("INSERT INTO operations (operationId, amount, currency, description) VALUES (:operationId, :amount, :currency, :description)")

        with engine.begin() as connection:
            connection.execute(query, data_dict)
            create_event(connection, data_dict['operationId'], None, STATUS_CREATED)

        data_dict["status"] = format_status(STATUS_CREATED)
        data_dict["providerPaymentId"] = None
        data_dict["amount"] = format_amount(data_dict["amount"])

        return data_dict
    except exc.IntegrityError as e:
        if e.orig and len(e.orig.args) > 0 and e.orig.args[0] == 1062:
            return Response(status_code=status.HTTP_409_CONFLICT)
        else:
            raise e
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def submit_operation_service(id: str, request: Request):
    try:
        query = text("UPDATE operations SET status = :toStatus WHERE operationId = :id AND status = :fromStatus")
        param_dict = {"toStatus": STATUS_PROCESSING, "id": id, "fromStatus": STATUS_CREATED}

        with engine.begin() as connection:
            result = connection.execute(query, param_dict)

            if result.rowcount > 0:
                create_event(connection, id, STATUS_CREATED, STATUS_PROCESSING)
                mp_queue = request.app.state.queue

                if mp_queue:
                    # Основной процесс FastAPI мгновенно добавляет ID в очередь и не ждет обработки
                    mp_queue.put(id)

                return Response(status_code=status.HTTP_202_ACCEPTED)

        return get_operation_data(id)
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def unlock_operation(operation_id: str):
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE operations SET isLockedForSubmit = 0 WHERE operationId = :operationId"), {'operationId': operation_id})


def create_event(connection, operation_id, from_status, to_status):
    event_dict = {
        'operationId': operation_id,
        'fromStatus': from_status,
        'toStatus': to_status,
        'type': to_status,
        'occurredAt': int(time.time())
    }

    if to_status == STATUS_CREATED:
        message = 'Operation created'
    elif to_status == STATUS_PROCESSING:
        message = 'Operation submitted'
    elif to_status == STATUS_COMPLETED:
        message = 'Operation completed'
    elif to_status == STATUS_REJECTED:
        message = 'Operation rejected'
    else:
        raise RuntimeError("Unexpected to_status parameter:" + str(to_status))

    event_dict['message'] = message
    query = text("INSERT INTO events (operationId, type, fromStatus, toStatus, occurredAt, message) VALUES (:operationId, :type, :fromStatus, :toStatus, :occurredAt, :message)")
    connection.execute(query, event_dict)


def finalize_operation_service(receipt_data: dict[str, str]):
    if receipt_data['result'] == 'COMPLETED':
        to_status = STATUS_COMPLETED
    elif receipt_data['result'] == 'REJECTED':
        to_status = STATUS_REJECTED
    else:
        return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if (
        'operationId' not in receipt_data
        or 'providerPaymentId' not in receipt_data
    ):
        return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    check_query = text("SELECT providerPaymentId FROM operations WHERE operationId = :operationId")

    query = text(f"UPDATE operations SET status = :status, providerPaymentId = COALESCE(providerPaymentId, :providerPaymentId) WHERE operationId = :operationId AND status = {STATUS_PROCESSING} AND COALESCE(providerPaymentId, :providerPaymentId) = :providerPaymentId")
    param_dict = {
        'status': to_status,
        'operationId': receipt_data['operationId'],
        'providerPaymentId': receipt_data['providerPaymentId']
    }
    receipt_dict = {
        'isIgnored': 0,
        'message': None,
        'occurredAt': None,
        'rawOccurredAt': None,
        'receiptResult': receipt_data['result'],
        'operationId': receipt_data['operationId'],
        'providerPaymentId': receipt_data['providerPaymentId'],
    }

    if 'message' in receipt_data:
        receipt_dict['message'] = receipt_data['message']

    if 'occurredAt' in receipt_data:
        receipt_dict['rawOccurredAt'] = receipt_data['occurredAt']

        if isinstance(receipt_data['occurredAt'], str):
            try:
                receipt_dict['occurredAt'] = int(datetime.datetime.fromisoformat(receipt_data['occurredAt'].replace('Z', '+00:00')).timestamp())
            except Exception as e:
                pass

    with engine.begin() as connection:
        try:
            result = connection.execute(query, param_dict)

            if result.rowcount == 1:
                create_event(connection, receipt_data['operationId'], STATUS_PROCESSING, to_status)
            else:
                row = connection.execute(check_query, param_dict).mappings().one_or_none()

                if row is None:
                    return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

                if row['providerPaymentId'] is not None and row['providerPaymentId'] != receipt_data['providerPaymentId']:
                    return Response(status_code=status.HTTP_409_CONFLICT)

                receipt_dict['isIgnored'] = 1

            query = text("INSERT INTO receipts (isIgnored, message, occurredAt, rawOccurredAt, receiptResult, operationId, providerPaymentId) VALUES (:isIgnored, :message, :occurredAt, :rawOccurredAt, :receiptResult, :operationId, :providerPaymentId)")
            connection.execute(query, receipt_dict)

            if receipt_dict['isIgnored'] == 1:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return {"status": "error", "detail": str(e)}


def basic_metrics_service(from_timestamp: int, to_timestamp: int):
    query = text(f"SELECT o.status, COUNT(o.operationId) AS cnt, SUM(o.amount) AS total FROM events e LEFT JOIN operations o ON o.operationId = e.operationId WHERE e.toStatus = {STATUS_PROCESSING} AND e.occurredAt BETWEEN {from_timestamp} AND {to_timestamp} GROUP BY o.status")

    try:
        with engine.begin() as connection:
            result = connection.execute(query)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    result_dict = {row["status"]: dict(row) for row in result.mappings()}

    if len(result_dict) == 0:
        return {
            'Approval Rate': 'N/A',
            'Rejection Rate': 'N/A',
            'Total Processed Volume (TPV)': '0.00 RUB',
            'Lost Revenue': '0.00 RUB',
            'Average Transaction Value (ATV)': 'N/A'
        }

    processing_cnt = result_dict[STATUS_PROCESSING]['cnt'] if STATUS_PROCESSING in result_dict else 0
    completed_cnt = result_dict[STATUS_COMPLETED]['cnt'] if STATUS_COMPLETED in result_dict else 0
    rejected_cnt = result_dict[STATUS_REJECTED]['cnt'] if STATUS_REJECTED in result_dict else 0
    total_cnt = processing_cnt + completed_cnt + rejected_cnt
    tpv = result_dict[STATUS_COMPLETED]['total'] if STATUS_COMPLETED in result_dict else 0
    lost_revenue = result_dict[STATUS_REJECTED]['total'] if STATUS_REJECTED in result_dict else 0
    atv = tpv / total_cnt

    return {
        'Approval Rate': f"{(completed_cnt / total_cnt * 100):.1f}" + '%',
        'Rejection Rate': f"{(rejected_cnt / total_cnt * 100):.1f}" + '%',
        'Total Processed Volume (TPV)': f"{tpv:.2f}" + ' RUB',
        'Lost Revenue': f"{lost_revenue:.2f}" + ' RUB',
        'Average Transaction Value (ATV)': f"{atv:.2f}" + ' RUB',
    }


def date_to_timestamp(the_date):
    dt_utc = datetime.datetime.combine(the_date, datetime.time.min, tzinfo=datetime.timezone.utc)

    return int(dt_utc.timestamp())
