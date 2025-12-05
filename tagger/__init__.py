"""
Anime Image Tagger Module

This module provides a unified interface for different anime image tagging backends.

Usage:
    # Using WD14 tagger (standalone implementation)
    from tagger import wd14
    result = wd14.get_tags("image.png")
    print(result.raw_string)
    
    # Using DGHS tagger (requires dghs-imgutils)
    from tagger import dghs
    if dghs.is_available():
        result = dghs.get_tags("image.png", model="wd14")
        print(result.raw_string)
    
    # Using class-based API
    from tagger.wd14 import WD14Tagger
    from tagger.dghs import DghsWD14Tagger, DghsMLDanbooruTagger
    
    tagger = WD14Tagger(model_name="wd-eva02-large-tagger-v3")
    result = tagger.get_tags("image.png")

Available Taggers:
    - wd14: Standalone WD14 implementation (no extra dependencies)
    - dghs: DGHS imgutils wrapper (requires: pip install dghs-imgutils)
        - DghsWD14Tagger: WD14 models via dghs
        - DghsMLDanbooruTagger: ML-Danbooru with 12,547 tags
"""

from .base import BaseTagger, TagResult
from . import wd14
from . import dghs

__all__ = [
    # Base classes
    "BaseTagger",
    "TagResult",
    # Modules
    "wd14",
    "dghs",
]


def get_default_tagger() -> BaseTagger:
    """
    Get the default tagger.
    
    Returns DGHS WD14 tagger if available, otherwise falls back to standalone WD14.
    """
    if dghs.is_available():
        return dghs.DghsWD14Tagger()
    return wd14.WD14Tagger()


def get_tags(image, threshold: float = 0.35, character_threshold: float = 0.85) -> TagResult:
    """
    Get tags for an image using the default tagger.
    
    Args:
        image: Path to image file or PIL Image object
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        TagResult object containing tags and metadata
    """
    tagger = get_default_tagger()
    return tagger.get_tags(image, threshold, character_threshold)
