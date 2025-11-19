import json
import os
import re
import zipfile
from typing import List, Tuple, Optional

import aiohttp
from PIL import Image
from apng import APNG

from parse_exception import ParseException
from utils import Downloader, DownloadDataEntry, get_rate_limiter
from config import PROXY, PIXIV_HEADER


def get_file_name_without_suffix(illust_code, illust_code_in_page, file_format):
    return f"pixiv_{illust_code}_p{illust_code_in_page}.{file_format}"


def convert_ugoira_to_apng(zip_path: str, delays: List[int], output_path: str):
    """
    Convert ugoira ZIP file to APNG and GIF formats.
    
    Args:
        zip_path: Path to the downloaded ZIP file
        delays: List of frame delays in milliseconds
        output_path: Path where the APNG file should be saved (GIF will be created alongside)
    """
    import tempfile
    import shutil
    
    # Create a temporary directory to extract frames
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extract all frames from ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Get sorted list of frame files
        frame_files = sorted([f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.png'))])
        
        if not frame_files:
            print(f"No frames found in {zip_path}")
            return
        
        # Convert JPG frames to PNG if necessary and load as PIL images
        png_frames = []
        pil_frames = []
        for i, frame_file in enumerate(frame_files):
            frame_path = os.path.join(temp_dir, frame_file)
            img = Image.open(frame_path)
            
            if frame_file.lower().endswith('.jpg'):
                # Convert JPG to PNG for APNG
                png_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                img.save(png_path, 'PNG')
                png_frames.append(png_path)
            else:
                png_frames.append(frame_path)
            
            # Convert to RGB for GIF (GIF doesn't support RGBA)
            if img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                pil_frames.append(background)
            elif img.mode != 'RGB':
                pil_frames.append(img.convert('RGB'))
            else:
                pil_frames.append(img.copy())
        
        # Ensure delays list matches frames count
        if len(delays) != len(png_frames):
            print(f"Warning: delays count ({len(delays)}) doesn't match frames count ({len(png_frames)})")
            # Repeat last delay if needed
            while len(delays) < len(png_frames):
                delays.append(delays[-1] if delays else 100)
        
        # Create APNG using the apng library
        apng = APNG()
        for frame_path, delay in zip(png_frames, delays):
            apng.append_file(frame_path, delay=delay)
        
        # Save APNG file
        apng.save(output_path)
        print(f"Successfully converted ugoira to APNG: {output_path}")
        
        # Create GIF file (for Windows thumbnail support)
        gif_path = output_path.rsplit('.', 1)[0] + '.gif'
        pil_frames[0].save(
            gif_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=delays,  # PIL expects duration in milliseconds
            loop=0,  # 0 means infinite loop
            optimize=False  # Don't optimize to preserve quality
        )
        print(f"Successfully converted ugoira to GIF: {gif_path}")
        
        # Remove the original ZIP file
        os.remove(zip_path)
        print(f"Removed original ZIP file: {zip_path}")
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _get_raw_file_urls(illust_code: str) -> Tuple[List[str],Optional[Tuple[str, List[int]]]]:
    async with aiohttp.ClientSession() as session:
        one_page_urls = await _get_one_page_urls(illust_code, session)
        if one_page_urls:
            ugoira_data = None
            if 'ugoira' in one_page_urls[0]:
                ugoira_data = await _get_ugoira_url(illust_code, session)
            return one_page_urls,ugoira_data

        _all_pages_urls = await _get_all_pages_urls(illust_code, session)
        if _all_pages_urls:
            return _all_pages_urls, None
    raise ParseException("raw parse failed", illust_code,f"https://www.pixiv.net/ajax/illust/{illust_code}")


async def _get_one_page_urls(illust_code: str, session: aiohttp.ClientSession) -> List[str]:
    index_url = f"https://www.pixiv.net/ajax/illust/{illust_code}"
    rate_limiter = get_rate_limiter()
    semaphore = await rate_limiter.acquire(index_url)
    try:
        async with session.get(index_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
            if response.status != 200:
                raise Exception(index_url + " " + str(response.status))
            html = await response.text()
            raw_data = json.loads(html)

            if raw_data['body']['pageCount'] == 1:
                print(f"parsed {index_url}")
                return [raw_data['body']['urls']['original']]
    finally:
        rate_limiter.release(index_url, semaphore)


async def _get_all_pages_urls(illust_code: str, session: aiohttp.ClientSession) -> List[str]:
    pages_url = f"https://www.pixiv.net/ajax/illust/{illust_code}/pages?lang=zh"
    rate_limiter = get_rate_limiter()
    semaphore = await rate_limiter.acquire(pages_url)
    try:
        async with session.get(pages_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
            if response.status != 200:
                raise Exception(pages_url + " " + str(response.status))
            html = await response.text()
            raw_data = json.loads(html)
            print(f"parsed {pages_url}")
            return list(map(lambda x: x['urls']['original'], raw_data['body']))
    finally:
        rate_limiter.release(pages_url, semaphore)


async def _get_ugoira_url(illust_code: str, session: aiohttp.ClientSession) -> Tuple[str, List[int]]:
    ugoira_meta_url = f"https://www.pixiv.net/ajax/illust/{illust_code}/ugoira_meta?lang=zh"
    rate_limiter = get_rate_limiter()
    semaphore = await rate_limiter.acquire(ugoira_meta_url)
    try:
        async with session.get(ugoira_meta_url, proxy=PROXY, headers=PIXIV_HEADER) as response:
            if response.status != 200:
                raise Exception(ugoira_meta_url + " " + str(response.status))
            html = await response.text()
            raw_data = json.loads(html)
            print(f"parsed {ugoira_meta_url}")
            url = raw_data['body']['originalSrc']
            if not url:
                raise ParseException("ugoira parse failed", ugoira_meta_url, html)
            # Extract frame delays from the response
            delays = [frame['delay'] for frame in raw_data['body']['frames']]
            return url, delays
    finally:
        rate_limiter.release(ugoira_meta_url, semaphore)


async def parse_pixiv(url, save_img_index_ls=None):
    print(f"parsing {url}")
    if save_img_index_ls is None:
        save_img_index_ls = [0]
    illust_code = re.search(
        r"https?://www.pixiv.net/artworks/(\d+)", url).group(1)

    illust_list, ugoira_data = await _get_raw_file_urls(illust_code)

    if not illust_list:
        raise ParseException("Adult content, login needed", url,
                             [get_file_name_without_suffix(illust_code, illust_code_in_page, 'png') for
                              illust_code_in_page in save_img_index_ls])

    header = {"Referer": "https://www.pixiv.net/"}
    download_entry_ls = []

    # 目前没在pixiv上见到多张ugoira
    for (image_index, image_url) in enumerate(illust_list):
        if save_img_index_ls and (image_index not in save_img_index_ls):
            continue
        file_format = image_url.rsplit(".", 1)[1]
        download_entry_ls.append(
            DownloadDataEntry(image_url, get_file_name_without_suffix(illust_code, image_index, file_format)))
    
    # Handle ugoira (animated illustrations)
    if not ugoira_data:
        await Downloader.get_downloader().submit_download_requests(download_entry_ls, url, header=header)
        return

    ugoira_url, delays = ugoira_data
    zip_filename = get_file_name_without_suffix(illust_code, 0, ugoira_url.rsplit(".", 1)[1])
    download_entry_ls.append(DownloadDataEntry(ugoira_url, zip_filename))

    # Submit downloads
    downloader = Downloader.get_downloader()
    await downloader.submit_download_requests(download_entry_ls, url, header=header)

    # Wait for downloads to complete
    await downloader.wait_for_tag_completion(url)

    # After download completes, convert ZIP to APNG
    from config import DEFAULT_DOWNLOAD_PATH
    zip_path = os.path.join(DEFAULT_DOWNLOAD_PATH, zip_filename)
    apng_filename = get_file_name_without_suffix(illust_code, 0, 'apng')
    apng_path = os.path.join(DEFAULT_DOWNLOAD_PATH, apng_filename)

    if os.path.exists(zip_path):
        convert_ugoira_to_apng(zip_path, delays, apng_path)
    else:
        print(f"Warning: ZIP file not found at {zip_path}, skipping conversion")