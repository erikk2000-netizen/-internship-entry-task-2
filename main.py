import asyncio
import multiprocessing
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text, exc
from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, Request, status

from database import engine
from worker import background_process_entry
from config import STATUS_PROCESSING
from routers import operations, receipts, health, metrics

# 2. Управление жизненным циклом FastAPI (Lifespan)
# Словарь для хранения глобального состояния (очереди)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаем процессо-безопасную очередь
    mp_queue = multiprocessing.Queue()
    app.state.queue = mp_queue

    with engine.begin() as connection:
        connection.execute(text(f"UPDATE operations SET isLockedForSubmit = 0 WHERE isLockedForSubmit = 1 AND status = {STATUS_PROCESSING}"))
        query = text(f"SELECT operationId FROM operations WHERE status = {STATUS_PROCESSING} AND isLockedForSubmit = 0")
        result = connection.execute(query)

    for row in result:
        mp_queue.put(row.operationId)

    # Запускаем фоновый процесс при старте FastAPI
    bg_process = multiprocessing.Process(
        target=background_process_entry, args=(mp_queue,)
    )
    bg_process.start()

    yield  # Здесь FastAPI работает и принимает запросы

    # Логика при выключении сервера (Shutdown)
    print("⏳ Завершение работы сервера, останавливаем фоновый процесс...")
    mp_queue.put(None)  # Отправляем сигнал остановки фоновому процессу

    # Ждем завершения фонового процесса в неблокирующем режиме
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, bg_process.join)
    print("✅ Фоновый процесс успешно остановлен.")


app = FastAPI(lifespan=lifespan)

app.include_router(health.router)
app.include_router(operations.router)
app.include_router(receipts.router)
app.include_router(metrics.router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )
