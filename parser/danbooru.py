"""
Danbooru parser for downloading images.
"""

import re

import aiohttp
from bs4 import BeautifulSoup, NavigableString

from .base import BaseParser, ParseResult, DownloadEntry
from utils import Downloader, DownloadDataEntry, get_rate_limiter
from config import PROXY


class DanbooruParser(BaseParser):
    """Parser for Danbooru images."""
    
    URL_PATTERN = r"https?://danbooru\.donmai\.us/posts/(\d+)"
    
    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a Danbooru URL.
        
        Args:
            url: Danbooru post URL
            
        Returns:
            ParseResult with download entries
        """
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

        tag_sidebar = soup.find("section", id="tag-list")
        stats_sidebar = soup.find("section", id="post-information")
        high_res_link = soup.find("li", id="post-option-download").find("a")

        artist_tag_elements = tag_sidebar.find("ul", class_="artist-tag-list").find_all("li")
        copyright_tag_elements = tag_sidebar.find("ul", class_="copyright-tag-list").find_all("li")
        character_tag_elements = tag_sidebar.find("ul", class_="character-tag-list").find_all("li")
        general_tag_elements = tag_sidebar.find("ul", class_="general-tag-list").find_all("li")

        stats_elements = stats_sidebar.findAll("li")

        def tag_attr_element_parser(entry_elements):
            entry_elements = [e for e in entry_elements if e.text.strip() != ""]
            return entry_elements[1].text, {
                "wiki_url": entry_elements[0].attrs["href"],
                "tag_url": entry_elements[1].attrs["href"],
                "tag_cnt": entry_elements[2].text
            }

        def statistics_element_parser(entry_elements):
            text = "".join((map(lambda x: x.text, entry_elements)))
            if text.startswith("Source"):
                return "Source", entry_elements.contents[1].attrs["href"]
            k, v = re.split(r":\s*", text, 1)
            return k, v

        tags_name_ls = ["Artist", "Copyright", "Tag"]
        tags_ls = [artist_tag_elements, copyright_tag_elements, character_tag_elements, general_tag_elements]
        tags = {tag_name: dict(map(tag_attr_element_parser, tag_elements))
                for tag_name, tag_elements in zip(tags_name_ls, tags_ls)}
        statistics = dict(map(statistics_element_parser, stats_elements))
        media_url = high_res_link.attrs["href"]

        artist = list(tags["Artist"].keys())[0] if tags["Artist"] else "unknown"
        source = statistics.get("Source", "unknown")
        illust_code = statistics["ID"]
        media_format = media_url.rsplit(".", 1)[-1]

        clean_source = self.clean_source_url(source)
        filename = f"danbooru_{illust_code}_{artist}_{clean_source}.{media_format}"

        return ParseResult(
            download_entries=[DownloadEntry(url=media_url, filename=filename)],
            source_url=url,
            tags=tags,
            artist=artist,
            original_source=source,
            metadata={"statistics": statistics, "illust_code": illust_code}
        )


# Legacy function for backward compatibility
async def parse_danbooru(url):
    """Legacy function - use DanbooruParser class instead."""
    parser = DanbooruParser()
    result = await parser.parse(url)
    
    # Convert to legacy format and submit
    download_entry_ls = [
        DownloadDataEntry(entry.url, entry.filename)
        for entry in result.download_entries
    ]
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)
