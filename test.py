import asyncio

from gelbooru_parser import parse_gelbooru


async def test():
    # pixiv
    await parse_gelbooru(
        "https://gelbooru.com/index.php?page=post&s=view&id=6653129&tags=red_eyes+white_hair+white_dress+1girl+")
    #twitter
    await parse_gelbooru("https://gelbooru.com/index.php?page=post&s=view&id=6659883&tags=red_eyes+white_hair+white_dress+1girl+")
    # # no source media
    # await parse_gelbooru("https://gelbooru.com/index.php?page=post&s=view&id=5962184")
    # unknown source format
    await parse_gelbooru("https://gelbooru.com/index.php?page=post&s=view&id=6665154&tags=red_eyes+white_hair+white_dress+1girl+")



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
