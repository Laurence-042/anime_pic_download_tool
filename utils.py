import asyncio
import os
from asyncio import sleep
from typing import List, Dict

import aiohttp

from config import DEFAULT_DOWNLOAD_PATH, DOWNLOAD_THREAD_NUM, COROUTINE_THREAD_LOOP, SLEEP_SECONDS_BETWEEN_BATCH


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
                asyncio.run_coroutine_threadsafe(self.download_pic(request, tag, header), COROUTINE_THREAD_LOOP)
            await sleep(SLEEP_SECONDS_BETWEEN_BATCH)

    async def download_pic(self, download_request: DownloadDataEntry, tag: str, header: Dict[str, str]):
        if os.path.exists(download_request.file_path) and os.path.getsize(download_request.file_path) > 0:
            self.tag_counter_dict[tag] = (self.tag_counter_dict[tag][0] + 1, self.tag_counter_dict[tag][1])
            if self.tag_counter_dict[tag][0] == self.tag_counter_dict[tag][1]:
                del self.tag_counter_dict[tag]
            print(f"{download_request.url} exist tag:{tag} {self.tag_counter_dict[tag][0]}/{self.tag_counter_dict[tag][1]}")
            return

        async with aiohttp.ClientSession(headers=header) as session:
            response = await session.get(download_request.url)
            if response.status != 200:
                raise Exception(download_request.url + " " + str(response.status))
            content = await response.read()

        with open(download_request.file_path, 'wb') as f:
            f.write(content)

        download_status = self.tag_counter_dict[tag]
        new_download_status = (download_status[0] + 1, download_status[1])
        if new_download_status[0] == new_download_status[1]:
            del self.tag_counter_dict[tag]
        else:
            self.tag_counter_dict[tag] = new_download_status
        print(f"{download_request.url} ok tag:{tag} {new_download_status[0]}/{new_download_status[1]}")
