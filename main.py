import asyncio
import logging
import sys
from asyncio import sleep

import config
from danbooru_parser import parse_danbooru
from gelbooru_parser import parse_gelbooru
from parse_exception import ParseException
from pixiv_parser import parse_pixiv
from twitter_parser import parse_twitter
from yandere_parser import parse_yandere

_failed = []
async def downloader(url: str, save_img_index_tp: tuple):
    try:
        if url.startswith("https://www.pixiv.net"):
            await parse_pixiv(url, save_img_index_tp)
        elif url.startswith("https://twitter.com"):
            await parse_twitter(url.split("?", 1)[0], save_img_index_tp)
        elif url.startswith("https://x.com"):
            await parse_twitter(url.split("?", 1)[0], save_img_index_tp)
        elif url.startswith("https://gelbooru.com"):
            await parse_gelbooru(url)
        elif url.startswith("https://yande.re"):
            await parse_yandere(url)
        elif url.startswith("https://danbooru.donmai.us"):
            await parse_danbooru(url)
        else:
            print(f"\033[31mno support\033[0m:{url}")
    except ParseException as e:
        logging.exception(e)
        _failed.append(url)
    except Exception as e:
        print(f"\033[31mException raised while parsing\033[0m:{url}")
        logging.exception(e)
        _failed.append(url)


async def wait_loop_end():
    while len(asyncio.all_tasks(config.COROUTINE_THREAD_LOOP)) > 0:
        await sleep(1)


def get_input_from_cli():
    in_lines = []
    print("input links, q to finish.")
    while True:
        line = input()
        if line.strip() == "q":
            break
        if line.startswith(" ") or line.strip() == "":
            continue
        in_lines.append(line)

    return in_lines


def get_input_from_file(file_name):
    with open(file_name, "r", encoding="utf8") as f:
        return f.readlines()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        in_lines = get_input_from_file(sys.argv[1])
    else:
        in_lines = get_input_from_cli()

    raw_in = filter(lambda x: x.startswith("http"), in_lines)
    raw_in = map(lambda x: x.strip(), raw_in)
    raw_in = map(lambda x: x.split(" ", 1), raw_in)
    raw_in = map(lambda x: (x[0], tuple(map(int, x[1].split())) if x[1]!="all" else tuple()) if len(x) > 1 else (x[0], None), raw_in)
    url_ls = list(raw_in)

    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    tasks = [asyncio.ensure_future(downloader(url, want_index_tp)) for url, want_index_tp in url_ls]
    new_loop.run_until_complete(asyncio.wait(tasks))
    new_loop.run_until_complete(wait_loop_end())

    config.COROUTINE_THREAD_LOOP.call_soon_threadsafe(config.COROUTINE_THREAD_LOOP.stop)

    if _failed:
        print("=======FAILED==========")
        for url in _failed:
            print(url)
