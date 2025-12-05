"""
Website Parser Module

This module provides a unified interface for parsing different anime/image websites.

Usage:
    # Using specific parser
    from parser import pixiv, danbooru, gelbooru, yandere, twitter
    
    result = await pixiv.PixivParser().parse("https://www.pixiv.net/artworks/12345")
    for entry in result.download_entries:
        print(f"Download: {entry.url} -> {entry.filename}")
    
    # Using auto-detection
    from parser import get_parser, parse_url
    
    parser = get_parser("https://www.pixiv.net/artworks/12345")
    if parser:
        result = await parser.parse(url)
    
    # Or use convenience function
    result = await parse_url("https://danbooru.donmai.us/posts/12345")

Available Parsers:
    - PixivParser: For pixiv.net artwork URLs
    - DanbooruParser: For danbooru.donmai.us post URLs  
    - GelbooruParser: For gelbooru.com post URLs
    - YandereParser: For yande.re post URLs
    - TwitterParser: For twitter.com/x.com status URLs

Legacy Functions (for backward compatibility):
    - parse_pixiv()
    - parse_danbooru()
    - parse_gelbooru()
    - parse_yandere()
    - parse_twitter()
"""

from typing import Optional, Type, List

from .base import BaseParser, ParseResult, DownloadEntry
from .pixiv import PixivParser, parse_pixiv
from .danbooru import DanbooruParser, parse_danbooru
from .gelbooru import GelbooruParser, parse_gelbooru
from .yandere import YandereParser, parse_yandere
from .twitter import TwitterParser, parse_twitter

__all__ = [
    # Base classes
    "BaseParser",
    "ParseResult",
    "DownloadEntry",
    # Parser classes
    "PixivParser",
    "DanbooruParser",
    "GelbooruParser",
    "YandereParser",
    "TwitterParser",
    # Legacy functions
    "parse_pixiv",
    "parse_danbooru",
    "parse_gelbooru",
    "parse_yandere",
    "parse_twitter",
    # Utility functions
    "get_parser",
    "get_all_parsers",
    "parse_url",
]

# Registry of all parsers
PARSERS: List[Type[BaseParser]] = [
    PixivParser,
    DanbooruParser,
    GelbooruParser,
    YandereParser,
    TwitterParser,
]


def get_parser(url: str) -> Optional[BaseParser]:
    """
    Get the appropriate parser for a URL.
    
    Args:
        url: The URL to find a parser for
        
    Returns:
        Parser instance if found, None otherwise
    """
    for parser_cls in PARSERS:
        if parser_cls.can_parse(url):
            return parser_cls()
    return None


def get_all_parsers() -> List[Type[BaseParser]]:
    """Get list of all available parser classes."""
    return PARSERS.copy()


async def parse_url(url: str, **kwargs) -> Optional[ParseResult]:
    """
    Parse a URL using the appropriate parser.
    
    Args:
        url: The URL to parse
        **kwargs: Additional arguments to pass to the parser
        
    Returns:
        ParseResult if successful, None if no parser found
    """
    parser = get_parser(url)
    if parser:
        return await parser.parse(url, **kwargs)
    return None
