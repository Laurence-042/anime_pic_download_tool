import json
import re

import aiohttp

from utils import Downloader, DownloadDataEntry


async def parse_pixiv(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [0]
    illust_code = re.search(r"https?://www.pixiv.net/artworks/(\d+)", url).group(1)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://www.pixiv.net/ajax/illust/{illust_code}?lang=zh") as response:
            if response.status != 200:
                raise Exception(url + " " + str(response.status))
            html = await response.text()
    raw_data = json.loads(html)
    print(f"parsed {url}")
    first_illust_url = raw_data['body']['urls']['original']
    illust_url_prefix, illust_url_suffix = first_illust_url.rsplit("0", 1)

    header = {"Referer": "https://www.pixiv.net/"}
    download_entry_ls = []
    for illust_index, illust_code_in_page in enumerate(save_img_index_ls):
        image_url = illust_url_prefix + str(illust_code_in_page) + illust_url_suffix
        file_format = image_url.rsplit(".", 1)[1]
        download_entry_ls.append(
            DownloadDataEntry(image_url, f"pixiv_{illust_code}_p{illust_code_in_page}.{file_format}"))
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url, header=header)
