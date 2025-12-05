"""
Gelbooru parser for downloading images.
"""

import re

import aiohttp
from bs4 import BeautifulSoup, NavigableString

from .base import BaseParser, ParseResult, DownloadEntry
from utils import Downloader, DownloadDataEntry, get_rate_limiter
from config import PROXY


class GelbooruParser(BaseParser):
    """Parser for Gelbooru images."""
    
    URL_PATTERN = r"https?://gelbooru\.com/index\.php\?.*id=(\d+)"
    
    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a Gelbooru URL.
        
        Args:
            url: Gelbooru post URL
            
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

        aside = soup.find("section", class_="aside").find_all("li")
        raw_post_attr_elements_dict = {
            "N/A": [[NavigableString("This key shouldn't be used.")]]
        }
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
                    list(filter(lambda x: x.text.strip() != "", entry.children))
                )

        def tag_attr_element_parser(entry_elements):
            return entry_elements[1].text, {
                "wiki_url": entry_elements[0].find("a").attrs["href"],
                "tag_url": entry_elements[1].attrs["href"],
                "tag_cnt": entry_elements[2].text
            }

        def statistics_element_parser(entry_elements):
            text = "".join((map(lambda x: x.text, entry_elements)))
            k, v = re.split(r":\s*", text, 1)
            return k, v

        tags_name_ls = ["Artist", "Copyright", "Metadata", "Tag"]
        tags = {
            tag_name: dict(map(tag_attr_element_parser, 
                              raw_post_attr_elements_dict.get(tag_name, [])))
            for tag_name in tags_name_ls
        }
        statistics = dict(map(statistics_element_parser, raw_post_attr_elements_dict["Statistics"]))
        media_url = list(filter(
            lambda x: x[0].text == "Original image", 
            raw_post_attr_elements_dict["Options"]
        ))[0][0].attrs["href"]

        artist = list(tags["Artist"].keys())[0] if tags["Artist"] else "unknown"
        source = statistics.get("Source", "unknown")
        illust_code = statistics["Id"]
        media_format = media_url.rsplit(".", 1)[-1]

        clean_source = self.clean_source_url(source)
        filename = f"gelbooru_{illust_code}_{artist}_{clean_source}.{media_format}"

        return ParseResult(
            download_entries=[DownloadEntry(url=media_url, filename=filename)],
            source_url=url,
            tags=tags,
            artist=artist,
            original_source=source,
            metadata={"statistics": statistics, "illust_code": illust_code}
        )


# Legacy function for backward compatibility
async def parse_gelbooru(url):
    """Legacy function - use GelbooruParser class instead."""
    parser = GelbooruParser()
    result = await parser.parse(url)
    
    download_entry_ls = [
        DownloadDataEntry(entry.url, entry.filename)
        for entry in result.download_entries
    ]
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)
