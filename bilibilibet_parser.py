import re

import bs4
from bs4 import BeautifulSoup

import aiohttp

from utils import Downloader, DownloadDataEntry


async def parse_bbb(url):
    print(f"parsing {url}")
    illust_code = re.search(r"https?://bilibili.bet/(\d+)", url).group(1)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(url + " " + str(response.status))
            html = await response.text()

    soup = BeautifulSoup(html, features="html.parser")
    print(f"parsed {url}")

    title = soup.find(class_=["post-header", "text-center"]).h1.text

    gallery = soup.find(class_="nc-light-gallery")
    image_url_ls = list(map(lambda x: x.attrs['src'], filter(lambda x: isinstance(x, bs4.Tag), gallery.children)))

    download_entry_ls = []
    for illust_index, image_url in enumerate(image_url_ls):
        file_format = image_url.rsplit(".", 1)[1]
        download_entry_ls.append(
            DownloadDataEntry(image_url, f"bilibili_bet_{illust_code}_p{illust_index}.{file_format}"))
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url, sub_dir_name=title)
