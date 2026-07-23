import asyncio
import multiprocessing

from services import operation_submit_service

async def async_consumer(mp_queue: multiprocessing.Queue):
    loop = asyncio.get_running_loop()

    while True:
        # Извлекаем ID без блокировки основного asyncio-цикла фонового процесса
        operation_id = await loop.run_in_executor(None, mp_queue.get)

        # Сигнал для мягкого завершения процесса
        if operation_id is None:
            break

        operation_submit_service(operation_id)


def background_process_entry(mp_queue: multiprocessing.Queue):
    """Точка входа для multiprocessing.Process"""
    asyncio.run(async_consumer(mp_queue))

