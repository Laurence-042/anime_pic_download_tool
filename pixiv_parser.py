import json
import re
from typing import List

import aiohttp

from parse_exception import ParseException
from utils import Downloader, DownloadDataEntry
from config import PROXY, PIXIV_HEADER


def get_file_name_without_suffix(illust_code, illust_code_in_page, file_format):
    return f"pixiv_{illust_code}_p{illust_code_in_page}.{file_format}"


async def _get_raw_file_urls(illust_code: str) -> List[str]:
    async with aiohttp.ClientSession() as session:
        one_page_urls = await _get_one_page_urls(illust_code, session)
        if one_page_urls:
            if 'ugoira' not in one_page_urls[0]:
                return one_page_urls
            else:
                return one_page_urls + await _get_ugoira_urls(illust_code, session)

        _all_pages_urls = await _get_all_pages_urls(illust_code, session)
        if _all_pages_urls:
            return _all_pages_urls
    raise ParseException("raw parse failed", illust_code,f"https://www.pixiv.net/ajax/illust/{illust_code}")


async def _get_one_page_urls(illust_code: str, session: aiohttp.ClientSession) -> List[str]:
    index_url = f"https://www.pixiv.net/ajax/illust/{illust_code}"
    async with session.get(index_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
        if response.status != 200:
            raise Exception(index_url + " " + str(response.status))
        html = await response.text()
        raw_data = json.loads(html)

        if raw_data['body']['pageCount'] == 1:
            print(f"parsed {index_url}")
            return [raw_data['body']['urls']['original']]


async def _get_all_pages_urls(illust_code: str, session: aiohttp.ClientSession) -> List[str]:
    pages_url = f"https://www.pixiv.net/ajax/illust/{illust_code}/pages?lang=zh"
    async with session.get(pages_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
        if response.status != 200:
            raise Exception(pages_url + " " + str(response.status))
        html = await response.text()
        raw_data = json.loads(html)
        print(f"parsed {pages_url}")
        return list(map(lambda x: x['urls']['original'], raw_data['body']))


async def _get_ugoira_urls(illust_code: str, session: aiohttp.ClientSession) -> List[str]:
    ugoira_meta_url = f"https://www.pixiv.net/ajax/illust/{illust_code}/ugoira_meta?lang=zh"
    async with session.get(ugoira_meta_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
        if response.status != 200:
            raise Exception(ugoira_meta_url + " " + str(response.status))
        html = await response.text()
        raw_data = json.loads(html)
        print(f"parsed {ugoira_meta_url}")
        url = raw_data['body']['originalSrc']
        if not url:
            raise ParseException("ugoira parse failed", ugoira_meta_url, html)
        return [url]


async def parse_pixiv(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [0]
    illust_code = re.search(
        r"https?://www.pixiv.net/artworks/(\d+)", url).group(1)

    illust_list = await _get_raw_file_urls(illust_code)

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
