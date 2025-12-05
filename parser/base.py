"""
Base class for website parsers.

All parser implementations should inherit from BaseParser and implement the parse method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import re


@dataclass
class ParseResult:
    """Result of parsing a URL."""
    # List of download entries
    download_entries: List['DownloadEntry']
    # Parsed tags (if available)
    tags: Dict[str, Any] = None
    # Source URL
    source_url: str = ""
    # Artist name (if available)
    artist: Optional[str] = None
    # Original source (if available, e.g., pixiv source from danbooru)
    original_source: Optional[str] = None
    # Any additional metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DownloadEntry:
    """A single download entry."""
    url: str
    filename: str
    # Optional custom headers for download
    headers: Dict[str, str] = None
    # Post-download callback (e.g., for ugoira conversion)
    post_process: Any = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class BaseParser(ABC):
    """Base class for all parsers."""
    
    # URL pattern this parser handles (regex)
    URL_PATTERN: str = None
    
    @classmethod
    def can_parse(cls, url: str) -> bool:
        """Check if this parser can handle the given URL."""
        if cls.URL_PATTERN is None:
            return False
        return re.search(cls.URL_PATTERN, url) is not None
    
    @abstractmethod
    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a URL and return download information.
        
        Args:
            url: The URL to parse
            **kwargs: Additional parser-specific options
            
        Returns:
            ParseResult object containing download entries and metadata
        """
        pass
    
    @classmethod
    def get_parser_name(cls) -> str:
        """Get the parser name."""
        return cls.__name__.replace("Parser", "").lower()
    
    @staticmethod
    def clean_source_url(source: str) -> str:
        """Clean and normalize a source URL for use in filenames."""
        if not source:
            return "unknown"
        
        source = source.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Handle known sources
        if source.startswith("pixiv.net"):
            return "pixiv_" + source.rsplit("/", 1)[-1]
        elif source.startswith("twitter.com") or source.startswith("x.com"):
            match = re.search(r"(?:twitter|x).com/([^/]+)/status/(\d+)", source)
            if match:
                return f"twitter_{match.group(1)}_{match.group(2)}"
        
        return source.replace("/", "_")
