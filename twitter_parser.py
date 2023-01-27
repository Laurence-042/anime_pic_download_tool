import asyncio
import re
from weakref import proxy

from pyppeteer import launch
from pyppeteer.network_manager import Response

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


async def deal_response(response: Response, url, post_code, post_author, save_img_index_ls):
    if not response.url.startswith("https://api.twitter.com/graphql"):
        return
    core_data = await response.json()

    print(f"parsed {url}")

    raw_data_pack = core_data['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']
    raw_data_pack = list(
        filter(lambda x: x['entryId'] == f"tweet-{post_code}", raw_data_pack))[0]

    try:
        raw_data_pack = raw_data_pack['content']['itemContent']['tweet_results']['result']['legacy']
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


async def parse_twitter(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [1]
    post_url_search_res = re.search(
        r"https://twitter.com/([^/]+)/status/(\d+)", url)
    post_author = post_url_search_res.group(1)
    post_code = post_url_search_res.group(2)

    # print("waiting launch")
    if PROXY:
        browser = await launch({'args': [f'--proxy-server={PROXY}'], 'headless': True})
    else:
        browser = await launch({'headless': True})
    # browser = await launch(
    #     devtools=True,
    #     headless=False,
    #     args=['--no-sandbox'],
    #     autoClose=False
    # )
    # print("waiting newPage")
    page = await browser.newPage()
    # print("waiting goto")
    # page.on('request', lambda request: asyncio.ensure_future(pyppeteer_request_debug(request)))
    # page.on('response', lambda response: asyncio.ensure_future(pyppeteer_response_debug(response)))

    page.on('response', lambda response: asyncio.ensure_future(
        deal_response(response, url, post_code, post_author, save_img_index_ls)))
    # print("waiting Response")
    await page.goto(url)
    # print("waiting json")
    # core_data = await core_response.buffer()
    await page.close()
