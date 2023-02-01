class ParseException(Exception):
    def __init__(self, reason, url, recommend_name):
        self.reason = reason
        self.url = url
        self.recommend_name = recommend_name

    def __str__(self) -> str:
        return f"\033[31m{self.reason}\033[0m:{self.url}    {self.recommend_name}"
