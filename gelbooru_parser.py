import re

import aiohttp
from bs4 import BeautifulSoup, NavigableString

from utils import Downloader, DownloadDataEntry, get_rate_limiter
from config import PROXY


async def parse_gelbooru(url):
    print(f"parsing {url}")

    rate_limiter = get_rate_limiter()
    semaphore = await rate_limiter.acquire(url)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=PROXY) as response:
                if response.status != 200:
                    raise Exception(url + " " + str(response.status))
                html = await response.text()
    finally:
        rate_limiter.release(url, semaphore)

    soup = BeautifulSoup(html, features="html.parser")
    print(f"parsed {url}")

    aside = soup.find("section", class_="aside").find_all("li")
    raw_post_attr_elements_dict = {
        "N/A": [[NavigableString("This key shouldn't be used. If it is, fix the gelbooru parser.")]]}
    attr_header = "N/A"
    for entry in aside:
        potential_attr_header = entry.find("b")
        if potential_attr_header is None:
            potential_attr_header = entry.find("h3")

        if potential_attr_header is not None:
            attr_header = potential_attr_header.text
            raw_post_attr_elements_dict[attr_header] = []
        elif entry.text.strip() != "":

            raw_post_attr_elements_dict[attr_header].append(
                list(filter(lambda x: x.text.strip() != "",
                            entry.children))
            )

    def tag_attr_element_parser(entry_elements):
        return entry_elements[1].text, {"wiki_url": entry_elements[0].find("a").attrs["href"],
                                        "tag_url": entry_elements[1].attrs["href"],
                                        "tag_cnt": entry_elements[2].text}

    def statistics_element_parser(entry_elements):
        text = "".join((map(lambda x: x.text, entry_elements)))
        k, v = re.split(r":\s*", text, 1)
        return k, v

    tags_name_ls = ["Artist", "Copyright", "Metadata", "Tag"]
    tags = {tag_name: dict(map(tag_attr_element_parser, raw_post_attr_elements_dict[
        tag_name] if tag_name in raw_post_attr_elements_dict else [])) for tag_name in tags_name_ls}
    statistics = dict(map(statistics_element_parser,
                      raw_post_attr_elements_dict["Statistics"]))
    media_url = list(filter(lambda x: x[0].text == "Original image", raw_post_attr_elements_dict["Options"]))[0][0] \
        .attrs["href"]

    post_attr_elements_dict = {
        "tags": tags,
        "statistics": statistics,
        "media_url": media_url
    }

    artist = list(tags["Artist"].keys())[0] if len(
        post_attr_elements_dict["tags"]["Artist"].keys()) != 0 else "unknown"
    source = post_attr_elements_dict["statistics"]["Source"] \
        if "Source" in post_attr_elements_dict["statistics"] else "unknown"
    illust_code = post_attr_elements_dict["statistics"]["Id"]
    media_url = post_attr_elements_dict["media_url"]
    media_format = media_url.rsplit(".", 1)[-1]

    source = source.replace(
        "https://", "").replace("http://", "").replace("www.", "")
    if source.startswith("pixiv.net"):
        source = "pixiv_" + source.rsplit("/", 1)[-1]
    elif source.startswith("twitter.com"):
        twitter_username, twitter_post_id = re.search(
            r"twitter.com/([^/]+)/status/(\d+)", source).groups()
        source = f"twitter_{twitter_username}_{twitter_post_id}"
    else:
        source = source.replace("/", "_")

    await Downloader.get_downloader().submit_download_requests(
        [DownloadDataEntry(media_url, f"gelbooru_{illust_code}_{artist}_{source}.{media_format}")], url)
