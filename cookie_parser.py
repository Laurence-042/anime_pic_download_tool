import time
from typing import List


def parse_cookie_from_export_cookie_file_plugin(file_path="x.com_cookies.txt"):
    with open(file_path, "r") as f:
        rows: List[str] = f.readlines()

    rows: map = map(lambda x: x.lstrip().rstrip("\n"), rows)
    rows: filter = filter(lambda x: x and not x.startswith("#"), rows)
    rows: List[str] = list(rows)

    res = []
    for row in rows:
        try:
            [domain, include_subdomains, path, secure, expiry, name, value] = row.split("\t")
            res.append({
                'name': name,
                'value': value,
                'domain': domain,
                'path': path,
                'expires': time.time() + 3600,
                'size': len(name) + len(value),
                'httpOnly': True,
                'secure': True,
                'session': False,
                'sameSite': 'Lax'
            })
        except Exception as e:
            print(e)

    return res
