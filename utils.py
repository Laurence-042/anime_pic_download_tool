import asyncio
import os
import time
from asyncio import sleep
from typing import List, Dict
from urllib.parse import urlparse

import aiohttp
from pyppeteer.network_manager import Response, Request

from config import DEFAULT_DOWNLOAD_PATH, DOWNLOAD_THREAD_NUM, COROUTINE_THREAD_LOOP, SLEEP_SECONDS_BETWEEN_BATCH, PROXY, RATE_LIMITS


class RateLimiter:
    """Rate limiter for controlling request frequency per domain"""
    
    def __init__(self):
        self.domain_limiters = {}
        self.domain_last_request = {}
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc
    
    def _get_limiter(self, domain: str):
        """Get or create rate limiter for a domain"""
        if domain not in self.domain_limiters:
            # Get rate limit config for this domain, or use default
            max_concurrent, min_interval = RATE_LIMITS.get(domain, (5, 0.3))
            self.domain_limiters[domain] = asyncio.Semaphore(max_concurrent)
            self.domain_last_request[domain] = 0
        return self.domain_limiters[domain], RATE_LIMITS.get(domain, (5, 0.3))[1]
    
    async def acquire(self, url: str):
        """Acquire permission to make a request to the given URL"""
        domain = self._get_domain(url)
        semaphore, min_interval = self._get_limiter(domain)
        
        # Wait for semaphore
        await semaphore.acquire()
        
        # Ensure minimum interval between requests
        current_time = time.time()
        last_request = self.domain_last_request.get(domain, 0)
        time_since_last = current_time - last_request
        
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)
        
        self.domain_last_request[domain] = time.time()
        return semaphore
    
    def release(self, url: str, semaphore):
        """Release the semaphore after request completion"""
        semaphore.release()


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return _rate_limiter



class DownloadDataEntry:
    url = ""
    file_path = ""

    def __init__(self, url, file_path=None):
        self.url = url
        if file_path is None:
            self.file_path = url.rsplit("/", 1)[-1]
        else:
            self.file_path = file_path

    def __str__(self):
        return f"url:{self.url},file_path:{self.file_path}"


class Downloader:
    thread_num = DOWNLOAD_THREAD_NUM

    tag_counter_dict = {}

    instance = None

    @classmethod
    def get_downloader(cls):
        if not Downloader.instance:
            Downloader.instance = Downloader()
        return Downloader.instance

    async def submit_download_requests(self, requests_ls: List[DownloadDataEntry], tag: str, sub_dir_name="",
                                       header=None):
        file_save_dir = os.path.join(DEFAULT_DOWNLOAD_PATH, sub_dir_name)
        if not os.path.exists(file_save_dir):
            os.makedirs(file_save_dir)

        while self.tag_counter_dict.get(tag) is not None:
            await sleep(SLEEP_SECONDS_BETWEEN_BATCH)
        self.tag_counter_dict[tag] = (0, len(requests_ls))

        for request in requests_ls:
            full_file_path = os.path.join(file_save_dir, request.file_path)
            request.file_path = full_file_path

        while len(requests_ls) > 0:
            request_batch = requests_ls[:self.thread_num]
            requests_ls = requests_ls[self.thread_num:]
            for request in request_batch:
                # print(request, tag)
                asyncio.run_coroutine_threadsafe(self.download_pic(
                    request, tag, header), COROUTINE_THREAD_LOOP)
            await sleep(SLEEP_SECONDS_BETWEEN_BATCH)

    async def download_pic(self, download_request: DownloadDataEntry, tag: str, header: Dict[str, str]):
        print(f"Ready to download {download_request.url}")
        if os.path.exists(download_request.file_path) and os.path.getsize(download_request.file_path) > 0:
            self.tag_counter_dict[tag] = (
                self.tag_counter_dict[tag][0] + 1, self.tag_counter_dict[tag][1])
            if self.tag_counter_dict[tag][0] == self.tag_counter_dict[tag][1]:
                del self.tag_counter_dict[tag]
            print(
                f"{download_request.url} exist tag:{tag} {self.tag_counter_dict[tag][0]}/{self.tag_counter_dict[tag][1]}")
            return

        rate_limiter = get_rate_limiter()
        semaphore = await rate_limiter.acquire(download_request.url)
        try:
            async with aiohttp.ClientSession(headers=header) as session:
                response = await session.get(download_request.url, proxy=PROXY)
                if response.status != 200:
                    print(f"\033[31mFaild tp dpwnlaod \033[0m:{download_request.url}")
                    raise Exception(download_request.url +
                                    " " + str(response.status))
                content = await response.read()
        finally:
            rate_limiter.release(download_request.url, semaphore)

        with open(download_request.file_path, 'wb') as f:
            f.write(content)

        download_status = self.tag_counter_dict[tag]
        new_download_status = (download_status[0] + 1, download_status[1])
        if new_download_status[0] == new_download_status[1]:
            del self.tag_counter_dict[tag]
        else:
            self.tag_counter_dict[tag] = new_download_status
        print(
            f"{download_request.url} ok tag:{tag} {new_download_status[0]}/{new_download_status[1]}")

async def pyppeteer_request_debug(request:Request):
    # Response logic goes here
    print("Request URL:", request.url)
    print("Method:", request.method)
    print("Request headers:", request.headers)
    # print("Request Headers:", response.request.headers)
    # print("Response status:", response.status)
    # if("json" in response.url):
    #     print("Response body:", await response.text())
    print("======")

async def pyppeteer_response_debug(response:Response):
    # Response logic goes here
    print("Response URL:", response.url)
    print("Method:", response.request.method)
    print("Response headers:", response.headers)
    # print("Request Headers:", response.request.headers)
    # print("Response status:", response.status)
    # if("json" in response.url):
    #     print("Response body:", await response.text())
    print("======")