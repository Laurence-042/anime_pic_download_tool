import re

import aiohttp
from bs4 import BeautifulSoup, NavigableString

from utils import Downloader, DownloadDataEntry
from config import PROXY


async def parse_danbooru(url):
    print(f"parsing {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=PROXY) as response:
            if response.status != 200:
                raise Exception(url + " " + str(response.status))
            html = await response.text()

    soup = BeautifulSoup(html, features="html.parser")
    print(f"parsed {url}")

    tag_sidebar = soup.find("section", id="tag-list")
    stats_sidebar = soup.find("section", id="post-information")
    high_res_link = soup.find("li", id="post-option-download").find("a")

    artist_tag_elements = tag_sidebar.find(
        "ul", class_="artist-tag-list").find_all("li")
    copyright_tag_elements = tag_sidebar.find(
        "ul", class_="copyright-tag-list").find_all("li")
    character_tag_elements = tag_sidebar.find(
        "ul", class_="character-tag-list").find_all("li")
    general_tag_elements = tag_sidebar.find(
        "ul", class_="general-tag-list").find_all("li")

    stats_elements = stats_sidebar.findAll("li")

    def tag_attr_element_parser(entry_elements):
        entry_elements = [e for e in entry_elements if e.text.strip() != ""]
        return entry_elements[1].text, {"wiki_url": entry_elements[0].attrs["href"],
                                        "tag_url": entry_elements[1].attrs["href"],
                                        "tag_cnt": entry_elements[2].text}

    def statistics_element_parser(entry_elements):
        text = "".join((map(lambda x: x.text, entry_elements)))
        if text.startswith("Source"):
            return "Source", entry_elements.contents[1].attrs["href"]
        k, v = re.split(r":\s*", text, 1)
        return k, v

    tags_name_ls = ["Artist", "Copyright", "Tag"]
    tags_ls = [artist_tag_elements, copyright_tag_elements,
               character_tag_elements, general_tag_elements]
    tags = {tag_name: dict(map(tag_attr_element_parser, tag_elements))
            for tag_name, tag_elements in zip(tags_name_ls, tags_ls)}
    statistics = dict(map(statistics_element_parser, stats_elements))
    media_url = high_res_link.attrs["href"]

    post_attr_elements_dict = {
        "tags": tags,
        "statistics": statistics,
        "media_url": media_url
    }

    artist = list(tags["Artist"].keys())[0] if len(
        post_attr_elements_dict["tags"]["Artist"].keys()) != 0 else "unknown"
    source = post_attr_elements_dict["statistics"]["Source"] \
        if "Source" in post_attr_elements_dict["statistics"] else "unknown"
    illust_code = post_attr_elements_dict["statistics"]["ID"]
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
        [DownloadDataEntry(media_url, f"danbooru_{illust_code}_{artist}_{source}.{media_format}")], url)
