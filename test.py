import asyncio
import aiohttp
from config import DEFAULT_DOWNLOAD_PATH, DOWNLOAD_THREAD_NUM, COROUTINE_THREAD_LOOP, SLEEP_SECONDS_BETWEEN_BATCH,PROXY

from twitter_parser import parse_twitter
from yandere_parser import parse_yandere


async def test_pixiv():
    header = {"Referer": "https://www.pixiv.net/"}
    url = "https://i.pximg.net/img-original/img/2020/08/22/18/00/01/83856875_p0.jpg"
    async with aiohttp.ClientSession(headers=header) as session:
        response = await session.get(url,proxy=PROXY)
        if response.status != 200:
            raise Exception(url + " " + str(response.status))
        content = await response.read()

async def test_twitter():
    url = "https://twitter.com/uminonaka0x0/status/1512007842534158339?s=09"
    await parse_twitter(url.split("?", 1)[0], 0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    tasks = [asyncio.ensure_future(test_twitter())]
    loop.run_until_complete(asyncio.wait(tasks))
