import base64

import aiohttp

from utils import Downloader, DownloadDataEntry


async def parse_jigex(url, save_img_index_ls=None):
    print(f"parsing {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(url + " " + str(response.status))
            real_url = str(response.url)
    params = {k: v for k, v in map(lambda x: x.split("="), real_url.split("?", 1)[1].split("&"))}
    img_page_url_base64 = params['url'].replace("~", "=")
    img_page_url = base64.b64decode(img_page_url_base64).decode("utf-8")
    img_url = img_page_url.split("_", 1)[0]
    print(f"parsed {url}")
    await Downloader.get_downloader().submit_download_requests([DownloadDataEntry(img_url)], url)
