import re

from pyppeteer import launch

from utils import Downloader, DownloadDataEntry


def extract_pic_download_entry(data_pack, save_index_in_post,post_author,post_code):
    media_url_https = data_pack['media_url_https'] + "?name=4096x4096"
    file_format = data_pack['media_url_https'].rsplit(".", 1)[1]
    return DownloadDataEntry(
            media_url_https,
            f"twitter_{post_author}_{post_code}_{save_index_in_post}.{file_format}"
        )

def extract_video_download_entry(data_pack, save_index_in_post,post_author,post_code):
    video_variants = list(filter(lambda x: x['content_type'] == "video/mp4", data_pack['video_info']['variants']))
    media_url_https = max(video_variants, key=lambda x: x['bitrate'])['url'].rsplit("?", 1)[0]
    file_format = media_url_https.rsplit(".", 1)[1]
    return DownloadDataEntry(
            media_url_https,
            f"twitter_{post_author}_{post_code}_{save_index_in_post}.{file_format}"
        )

async def parse_twitter(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [1]
    post_url_search_res = re.search(r"https://twitter.com/([^/]+)/status/(\d+)", url)
    post_author = post_url_search_res.group(1)
    post_code = post_url_search_res.group(2)

    # print("waiting launch")
    browser = await launch(headless=True)
    # print("waiting newPage")
    page = await browser.newPage()
    # print("waiting goto")
    await page.goto(url, waitUntil="domcontentloaded")
    # print("waiting Response")
    core_response = await page.waitForResponse(lambda x: x.url.startswith("https://twitter.com/i/api/graphql"))
    # print("waiting json")
    core_data = await core_response.json()
    await page.close()
    print(f"parsed {url}")

    raw_data_pack = core_data['data']['threaded_conversation_with_injections']['instructions'][0]['entries']
    raw_data_pack = list(filter(lambda x: x['entryId'] == f"tweet-{post_code}", raw_data_pack))[0]
    
    raw_data_pack = raw_data_pack['content']['itemContent']['tweet_results']['result']['legacy']
    
    raw_data_pack = raw_data_pack['extended_entities'] if 'extended_entities' in raw_data_pack else raw_data_pack['entities']
    raw_data_pack = raw_data_pack['media']

    raw_target_media_data_ls = [(save_img_index, raw_data_pack[save_img_index - 1]) for save_img_index in save_img_index_ls]

    download_entry_ls = []
    for save_img_index, data in raw_target_media_data_ls:
        if data['type'] == "photo":
            download_entry_ls.append(extract_pic_download_entry(data, save_img_index,post_author,post_code))
        elif data['type'] == "video" or data['type'] == "animated_gif":
            download_entry_ls.append(extract_video_download_entry(data, save_img_index,post_author,post_code))
        else:
            print(f"unknown type {data['type']} of url {url}")
            
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)

