import asyncio
import re
from collections import OrderedDict
from threading import Thread

DEFAULT_DOWNLOAD_PATH = "./download/"
DOWNLOAD_THREAD_NUM = 8
SLEEP_SECONDS_BETWEEN_BATCH = 3


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def parse_raw_header(raw_header):
    header_entries = raw_header.split("\n")
    kv_ls = list(map(lambda x:x.split(': ',1),filter(bool, header_entries)))
    res = OrderedDict()
    for k,v in kv_ls:
        res[k]=v
    return res



new_loop = asyncio.new_event_loop()
COROUTINE_THREAD = Thread(target=start_loop, args=(new_loop,))
COROUTINE_THREAD.start()

COROUTINE_THREAD_LOOP = new_loop
# PROXY = 'http://127.0.0.1:41091'
PROXY = None
# PROXY = 'http://127.0.0.1:2049'

PIXIV_HEADER = parse_raw_header("""accept: */*
accept-encoding: gzip, deflate, br
accept-language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6
cookie: first_visit_datetime_pc=2022-12-24+20%3A58%3A21; p_ab_id=2; p_ab_id_2=8; p_ab_d_id=691200625; __cf_bm=jaRCR9jxDvUZNVQqwuFFziFyAETmI7gcewEfjoiacpY-1671883102-0-AdfMuNw6MxRnlzs6tXMYaWCOtWHd78Lyw3PcT+u7uSBtRtOX4natO2wdQB+q8iB0il7cnvbAMSEU0Ykdz8WnB+Khr5tzg3gSyuKuhwkYGQE0vKBChrOfb82WNuU1QsKe6bnOnSLQZ7DHqlb2PxvQXC/xiTL+8KWLLyVPkFdwC3FJ+Qw1S0TDXGgQzfq1XjZMlczSzCXLXyjSxEV+IBDJ/sA=; PHPSESSID=30225036_VambpfS7UGr2DblfJKFnE4S04YELGDX6; device_token=f9eb44354b16f43b78d54e258fc82215; privacy_policy_agreement=5; c_type=24; privacy_policy_notification=0; a_type=0; b_type=1; yuid_b=N4Bgk5I; tag_view_ranking=Lt-oEicbBr~rOnsP2Q5UN~5oPIfUbtd6~cFXtS-flQO~7WfWkHyQ76~oJAJo4VO5E; QSI_S_ZN_5hF4My7Ad6VNNAi=v:0:0
referer: https://www.pixiv.net/artworks/103224506
sec-ch-ua: "Not?A_Brand";v="8", "Chromium";v="108", "Microsoft Edge";v="108"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "Windows"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.54
""")