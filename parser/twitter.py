"""
Twitter/X parser for downloading images and videos.
"""

import asyncio
import re
import time
from typing import Dict, List

from pyppeteer import launch
from pyppeteer.network_manager import Response

from .base import BaseParser, ParseResult, DownloadEntry
from cookie_parser import parse_cookie_from_export_cookie_file_plugin
from parse_exception import ParseException
from utils import Downloader, DownloadDataEntry, pyppeteer_request_debug, pyppeteer_response_debug
from config import PROXY


def get_file_name_without_suffix(save_index_in_post, post_author, post_code):
    return f"twitter_{post_author}_{post_code}_{save_index_in_post}"


def cookie_to_pyppeteer_ver(cookie: dict) -> Dict:
    return {
        'name': cookie.get('name'),
        'value': cookie.get('value'),
        'domain': cookie.get('domain'),
        'path': cookie.get('path'),
        'expires': int(time.time() + 3600),
        'httpOnly': True,
        'secure': True,
        'sameSite': 'Lax'
    }


def response_filter(response: Response) -> bool:
    if response.url.endswith(".js"):
        return False
    return (("TweetDetail" in response.url or "TweetResultByRestId" in response.url) 
            and response.request.method == "GET" 
            and response.status == 200)


def extract_pic_download_entry(data_pack, save_index_in_post, post_author, post_code) -> DownloadEntry:
    media_url_https = data_pack['media_url_https'] + "?name=4096x4096"
    file_format = data_pack['media_url_https'].rsplit(".", 1)[1]
    return DownloadEntry(
        url=media_url_https,
        filename=f"{get_file_name_without_suffix(save_index_in_post, post_author, post_code)}.{file_format}"
    )


def extract_video_download_entry(data_pack, save_index_in_post, post_author, post_code) -> DownloadEntry:
    video_variants = list(filter(
        lambda x: x['content_type'] == "video/mp4", 
        data_pack['video_info']['variants']
    ))
    media_url_https = max(video_variants, key=lambda x: x['bitrate'])['url'].rsplit("?", 1)[0]
    file_format = media_url_https.rsplit(".", 1)[1]
    return DownloadEntry(
        url=media_url_https,
        filename=f"{get_file_name_without_suffix(save_index_in_post, post_author, post_code)}.{file_format}"
    )


class TwitterParser(BaseParser):
    """Parser for Twitter/X posts."""
    
    URL_PATTERN = r"https://[^.]+\.com/([^/]+)/status/(\d+)"
    
    async def parse(self, url: str, save_img_index_ls: List[int] = None, **kwargs) -> ParseResult:
        """
        Parse a Twitter/X URL.
        
        Args:
            url: Twitter/X post URL
            save_img_index_ls: List of image indices to download (1-indexed)
            
        Returns:
            ParseResult with download entries
        """
        print(f"parsing {url}")
        if save_img_index_ls is None:
            save_img_index_ls = [1]
        
        post_url_search_res = re.search(self.URL_PATTERN, url)
        if not post_url_search_res:
            raise ParseException("Invalid Twitter URL", url, [])
        
        post_author = post_url_search_res.group(1)
        post_code = post_url_search_res.group(2)

        # Launch browser
        if PROXY:
            browser = await launch({
                'args': [f'--proxy-server={PROXY}', '--ignore-certificate-errors'], 
                'headless': False
            })
        else:
            browser = await launch({
                'args': ['--ignore-certificate-errors'], 
                'headless': False
            })

        page = await browser.newPage()
        
        # Set cookies
        edge_cookies = parse_cookie_from_export_cookie_file_plugin()
        twitter_cookies = list(map(cookie_to_pyppeteer_ver, edge_cookies))
        await page.setCookie(*twitter_cookies)

        # Navigate and capture response
        response, _ = await asyncio.gather(
            page.waitForResponse(response_filter),
            page.goto(url)
        )
        response_data: dict = await response.json()
        print(f"parsed {url}")
        await page.close()
        await browser.close()

        core_data: dict = response_data['data']

        try:
            if "tweetResult" in core_data:
                core_data = core_data['tweetResult']
            else:
                core_data = core_data['threaded_conversation_with_injections_v2']['instructions']
                core_data = next(item for item in core_data if item["type"] == "TimelineAddEntries")['entries']
                core_data = next(item for item in core_data if item['entryId'].startswith("tweet-"))[
                    'content']['itemContent']['tweet_results']
            core_data = core_data['result']
            if "tweet" in core_data:
                core_data = core_data["tweet"]
            raw_data_pack = core_data['legacy']
        except KeyError:
            raise ParseException(
                "Adult content, login needed", 
                url,
                [get_file_name_without_suffix(idx, post_author, post_code) for idx in save_img_index_ls]
            )

        raw_data_pack = (raw_data_pack.get('extended_entities') or 
                        raw_data_pack.get('entities', {}))
        raw_data_pack: List[dict] = raw_data_pack.get('media', [])

        raw_target_media_data_ls = [
            (save_img_index, raw_data_pack[save_img_index - 1])
            for save_img_index in save_img_index_ls
            if save_img_index <= len(raw_data_pack)
        ]

        download_entries = []
        for save_img_index, data in raw_target_media_data_ls:
            if data['type'] == "photo":
                download_entries.append(
                    extract_pic_download_entry(data, save_img_index, post_author, post_code)
                )
            elif data['type'] in ("video", "animated_gif"):
                download_entries.append(
                    extract_video_download_entry(data, save_img_index, post_author, post_code)
                )
            else:
                print(f"unknown type {data['type']} of url {url}")

        return ParseResult(
            download_entries=download_entries,
            source_url=url,
            metadata={
                "post_author": post_author,
                "post_code": post_code
            }
        )


# Legacy function for backward compatibility
async def parse_twitter(url, save_img_index_ls=None):
    """Legacy function - use TwitterParser class instead."""
    parser = TwitterParser()
    result = await parser.parse(url, save_img_index_ls)
    
    download_entry_ls = [
        DownloadDataEntry(entry.url, entry.filename)
        for entry in result.download_entries
    ]
    await Downloader.get_downloader().submit_download_requests(download_entry_ls, url)
