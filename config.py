import asyncio
import re
from collections import OrderedDict

DEFAULT_DOWNLOAD_PATH = "./download/"
DOWNLOAD_THREAD_NUM = 8
SLEEP_SECONDS_BETWEEN_BATCH = 3

# Rate limiting configuration for different domains
# Format: {domain: (max_concurrent_requests, min_interval_seconds)}
RATE_LIMITS = {
    "www.pixiv.net": (3, 0.5),  # Max 3 concurrent requests, 0.5s between requests
    "i.pximg.net": (5, 0.3),     # Pixiv CDN
    "gelbooru.com": (2, 0.5),
    "yande.re": (2, 0.5),
    "danbooru.donmai.us": (2, 0.5),
    "pbs.twimg.com": (5, 0.3),   # Twitter images
    "twitter.com": (2, 0.5),
    "x.com": (2, 0.5),
}


def parse_raw_header(raw_header):
    header_entries = raw_header.split("\n")
    kv_ls = list(map(lambda x:x.split(': ',1),filter(bool, header_entries)))
    res = OrderedDict()
    for k,v in kv_ls:
        res[k]=v
    return res


# PROXY = 'http://127.0.0.1:41091'
PROXY = None
# PROXY = 'http://127.0.0.1:2049'

PIXIV_HEADER = parse_raw_header("""accept: */*
accept-encoding: gzip
accept-language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6
cookie: first_visit_datetime_pc=2022-12-24+20%3A58%3A21; p_ab_id=2; p_ab_id_2=8; p_ab_d_id=691200625; privacy_policy_notification=0; a_type=0; b_type=1; yuid_b=N4Bgk5I; login_ever=yes; privacy_policy_agreement=6; c_type=25; PHPSESSID=84386758_ZTMAH9Jq62mMXqctyPKCJvZYjCVK4GH9; __cf_bm=zRMu_tH7zwm6lsa.Hxs.cUOgO3ordlabWoGXe8hw_jg-1706190044-1-AdHohFmNiPIti67cPLkbRcPlKOyJGeuiKT2oAYgh8INQpCK6mpWRDYF0nf2+GBIvVlPUWZh8Q4Wfab78ADboENXqxh+MiuA4Ly5uUlE4rpoe; cf_clearance=Ca0CkwY0dWlgSJdu_mWmJuzqwcKQP7wjGosZiYXxdhM-1706190046-1-Abcod8Zn7w6DkhjTH1R3xC2agCAYfY+dElUI1c63Az5v7EqpVzdhZ9VJv199s6ekxM4pAQwMAXIoJC4i6V8FKKQ=
referer: https://www.pixiv.net/artworks/103224506
sec-ch-ua: "Not?A_Brand";v="8", "Chromium";v="108", "Microsoft Edge";v="108"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "Windows"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.54
""")