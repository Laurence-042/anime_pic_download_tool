import json
import re
import urllib.parse
from weakref import proxy

import aiohttp

from parse_exception import ParseException
from utils import Downloader, DownloadDataEntry
from config import PROXY, PIXIV_HEADER


def get_file_name_without_suffix(illust_code, illust_code_in_page, file_format):
    return f"pixiv_{illust_code}_p{illust_code_in_page}.{file_format}"

async def parse_pixiv(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [0]
    illust_code = re.search(
        r"https?://www.pixiv.net/artworks/(\d+)", url).group(1)

    async with aiohttp.ClientSession() as session:
        url = f"https://www.pixiv.net/ajax/illust/{illust_code}/pages?lang=zh"
        async with session.get(url, proxy=PROXY,headers =PIXIV_HEADER) as response:
            if response.status != 200:
                raise Exception(url + " " + str(response.status))
            html = await response.text()
            raw_data = json.loads(html)
            illust_list = list(map(lambda x:x['urls']['original'],raw_data['body']))
    print(f"parsed {url}")

    if not illust_list:
        raise ParseException("Adult content, login needed", url,
                             [get_file_name_without_suffix(illust_code, illust_code_in_page, 'png') for
                              illust_code_in_page in save_img_index_ls])


    header = {"Referer": "https://www.pixiv.net/"}
    download_entry_ls = []
    for (image_index, image_url) in enumerate(illust_list):
        if save_img_index_ls and (image_index not in save_img_index_ls):
            continue
        file_format = image_url.rsplit(".", 1)[1]
        download_entry_ls.append(
            DownloadDataEntry(image_url, get_file_name_without_suffix(illust_code, image_index, file_format)))
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url, header=header)
