import asyncio
from asyncio import sleep

import config
from bilibilibet_parser import parse_bbb
from jigex_parser import parse_jigex

from pixiv_parser import parse_pixiv
from twitter_parser import parse_twitter


async def downloader(url: str, save_img_index_tp: tuple):
    try:
        if url.startswith("https://www.pixiv.net"):
            await parse_pixiv(url, save_img_index_tp)
        elif url.startswith("https://twitter.com"):
            await parse_twitter(url.split("?", 1)[0], save_img_index_tp)
        elif url.startswith("https://bilibili.bet"):
            await parse_bbb(url)
        elif url.startswith("https://jigex.com"):
            await parse_jigex(url)
        else:
            print(url, "no support")
    except Exception as e:
        print(e)


async def wait_loop_end():
    while len(asyncio.all_tasks(config.COROUTINE_THREAD_LOOP)) > 0:
        await sleep(1)


if __name__ == '__main__':
    in_lines = []
    print("input links, q to finish.")
    while True:
        line = input()
        if line.strip() == "q":
            break
        if line.startswith(" ") or line.strip() == "":
            continue
        in_lines.append(line)
    # with open("input.txt", "r", encoding="utf8") as f:
    #     raw_in = f.read()
    # in_lines = raw_in.splitlines(keepends=False)
    raw_in = filter(lambda x: not x.startswith("#"), in_lines)
    raw_in = map(lambda x: x.split(" ", 1), raw_in)
    raw_in = map(lambda x: (x[0], tuple(map(int, x[1].split()))) if len(x) > 1 else (x[0], None), raw_in)
    url_ls = list(raw_in)
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    loop = asyncio.get_event_loop()
    tasks = [asyncio.ensure_future(downloader(url, want_index_tp)) for url, want_index_tp in url_ls]
    loop.run_until_complete(asyncio.wait(tasks))
    loop.run_until_complete(wait_loop_end())

    config.COROUTINE_THREAD_LOOP.call_soon_threadsafe(config.COROUTINE_THREAD_LOOP.stop)
