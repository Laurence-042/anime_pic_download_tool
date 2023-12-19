import asyncio
import re
import time
from http.cookiejar import Cookie
from typing import Dict
from weakref import proxy

from pyppeteer import launch
from pyppeteer.network_manager import Response
import rookiepy

from parse_exception import ParseException
from utils import Downloader, DownloadDataEntry, pyppeteer_request_debug, pyppeteer_response_debug
from config import PROXY


def extract_pic_download_entry(data_pack, save_index_in_post, post_author, post_code):
    media_url_https = data_pack['media_url_https'] + "?name=4096x4096"
    file_format = data_pack['media_url_https'].rsplit(".", 1)[1]
    return DownloadDataEntry(
        media_url_https,
        f"{get_file_name_without_suffix(save_index_in_post, post_author, post_code)}.{file_format}"
    )


def extract_video_download_entry(data_pack, save_index_in_post, post_author, post_code):
    video_variants = list(filter(
        lambda x: x['content_type'] == "video/mp4", data_pack['video_info']['variants']))
    media_url_https = max(video_variants, key=lambda x: x['bitrate'])[
        'url'].rsplit("?", 1)[0]
    file_format = media_url_https.rsplit(".", 1)[1]
    return DownloadDataEntry(
        media_url_https,
        f"{get_file_name_without_suffix(save_index_in_post, post_author, post_code)}.{file_format}"
    )


def get_file_name_without_suffix(save_index_in_post, post_author, post_code):
    return f"twitter_{post_author}_{post_code}_{save_index_in_post}"


def cookie_to_pyppeteer_ver(cookie: dict) -> Dict:
    # return cookie
    return {
        'name': cookie.get('name'),
        'value': cookie.get('value'),
        'domain': cookie.get('domain'),
        'path': cookie.get('path'),
        'expires': time.time() + 3600,
        'size': len(cookie.get('name')) + len(cookie.get('value')),
        'httpOnly': True,
        'secure': True,
        'session': False,
        'sameSite': 'Lax'
    }


def response_filter(response: Response) -> bool:
    return response.url.startswith(
        "https://api.twitter.com/graphql/") and "TweetResultByRestId" in response.url and response.request.method == "GET"


async def parse_twitter(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [1]
    post_url_search_res = re.search(
        r"https://[^.]+.com/([^/]+)/status/(\d+)", url)
    post_author = post_url_search_res.group(1)
    post_code = post_url_search_res.group(2)

    # print("waiting launch")
    if PROXY:
        browser = await launch({'args': [f'--proxy-server={PROXY}', '--ignore-certificate-errors'], 'headless': False})
    else:
        browser = await launch({'args': ['--ignore-certificate-errors'],'headless': False})
    # browser = await launch(
    #     devtools=True,
    #     headless=False,
    #     args=['--no-sandbox'],
    #     autoClose=False
    # )
    # print("waiting newPage")
    page = await browser.newPage()
    # await page.goto('https://github.com/login')
    # await page.type('#login_field', 'laurence042')  # your user name here
    # await page.type('#password', 'Un4080210185')  # your password here
    # navPromise = asyncio.ensure_future(page.waitForNavigation())
    # await page.click('input[type=submit]')
    # await navPromise
    # cookies = await page.cookies()
    # await browser.close()

    # print("waiting Response")
    edge_cookies = rookiepy.edge()
    twitter_cookies = list(map(cookie_to_pyppeteer_ver, filter(lambda x: "twitter" in x['domain'] and "/" == x['path'], edge_cookies)))
    await page.setCookie(*twitter_cookies)

    # graphql api use 'option' as request method first, then use 'get' method to get response.
    # capture the 'get' response as data
    response, _ = await asyncio.gather(page.waitForResponse(response_filter),
                                       page.goto(url))
    core_data = await response.json()
    print(f"parsed {url}")
    await page.close()

    try:
        raw_data_pack = core_data['data']['tweetResult']['result']['legacy']
    except KeyError:
        raise ParseException("Adult content, login needed", url,
                             [get_file_name_without_suffix(save_index_in_post, post_author, post_code) for
                              save_index_in_post in save_img_index_ls])

    raw_data_pack = raw_data_pack['extended_entities'] if 'extended_entities' in raw_data_pack else raw_data_pack[
        'entities']
    raw_data_pack = raw_data_pack['media']

    raw_target_media_data_ls = [(save_img_index, raw_data_pack[save_img_index - 1])
                                for save_img_index in save_img_index_ls]

    download_entry_ls = []
    for save_img_index, data in raw_target_media_data_ls:
        if data['type'] == "photo":
            download_entry_ls.append(extract_pic_download_entry(
                data, save_img_index, post_author, post_code))
        elif data['type'] == "video" or data['type'] == "animated_gif":
            download_entry_ls.append(extract_video_download_entry(
                data, save_img_index, post_author, post_code))
        else:
            print(f"unknown type {data['type']} of url {url}")

    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)
    # await page.goto(url)
    # print("waiting json")
    # core_data = await core_response.buffer()
