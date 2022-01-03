import asyncio

from yandere_parser import parse_yandere


async def test():
    # pixiv without character tag
    await parse_yandere(
        "https://yande.re/post/show/889591")
    # no source with character tag
    await parse_yandere("https://yande.re/post/show/829310")



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
