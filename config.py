import asyncio
from threading import Thread

DEFAULT_DOWNLOAD_PATH = "./download/"
DOWNLOAD_THREAD_NUM = 8
SLEEP_SECONDS_BETWEEN_BATCH = 3


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


new_loop = asyncio.new_event_loop()
COROUTINE_THREAD = Thread(target=start_loop, args=(new_loop,))
COROUTINE_THREAD.start()

COROUTINE_THREAD_LOOP = new_loop
