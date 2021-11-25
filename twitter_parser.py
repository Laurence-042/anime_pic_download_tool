import re

from pyppeteer import launch

from utils import Downloader, DownloadDataEntry


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

    media_data_ls = core_data['data']['threaded_conversation_with_injections']['instructions'][0]['entries'][
        0]['content']['itemContent']['tweet_results']['result']['legacy']['entities']['media']
    target_media_data_ls = [(save_img_index, media_data_ls[save_img_index - 1]) for save_img_index in save_img_index_ls]

    download_entry_ls = []
    for illust_index, (save_img_index_in_post, media_data) in enumerate(target_media_data_ls):
        media_url_https = media_data['media_url_https'] + "?name=4096x4096"
        file_format = media_data['media_url_https'].rsplit(".", 1)[1]
        download_entry_ls.append(
            DownloadDataEntry(
                media_url_https,
                f"twitter_{post_author}_{post_code}_{save_img_index_in_post}.{file_format}"
            ))
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)

