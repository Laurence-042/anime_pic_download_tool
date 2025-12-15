"""
Anime Image Tagger Module

This module provides a unified interface for different anime image tagging backends.

Usage:
    # Using DGHS tagger (requires dghs-imgutils)
    from tagger import dghs
    if dghs.is_available():
        result = dghs.get_tags("image.png", model="EVA02_Large")
        print(result.raw_string)
    
    # Using Camie tagger (70,000+ tags including rating/general/character)
    from tagger import camie
    if camie.is_available():
        result = camie.get_tags("image.png")
        print(result.raw_string)
    
    # Using class-based API
    from tagger.dghs import DghsWD14Tagger, DghsMLDanbooruTagger
    from tagger.camie import CamieTagger
    
    # WD14 tagger (EVA02-Large recommended)
    tagger = DghsWD14Tagger(model_name="EVA02_Large")
    result = tagger.get_tags("image.png")
    
    # ML-Danbooru tagger (12,547 tags, Caformer architecture)
    tagger = DghsMLDanbooruTagger()
    result = tagger.get_tags("image.png")
    
    # Camie tagger (70,000+ tags)
    tagger = CamieTagger(mode='balanced')
    result = tagger.get_tags("image.png")

Available Taggers:
    - dghs: DGHS imgutils wrapper (requires: pip install dghs-imgutils)
        - DghsWD14Tagger: WD14 models (EVA02_Large, ViT_Large, etc.)
        - DghsMLDanbooruTagger: ML-Danbooru with 12,547 tags (Caformer)
    - camie: Camie tagger with 70,000+ tags (rating, general, character)
"""

from .base import BaseTagger, TagResult
from . import dghs
from . import camie
from . import camie_v2

__all__ = [
    # Base classes
    "BaseTagger",
    "TagResult",
    # Modules
    "dghs",
    "camie",
    "camie_v2",
    # Functions
    "is_available",
    "get_default_tagger",
    "get_tags",
]


def is_available() -> bool:
    """
    Check if any tagger backend is available.
    
    Returns:
        True if at least one tagger (dghs, camie, or camie_v2) is available.
    """
    return dghs.is_available() or camie.is_available() or camie_v2.is_available()


def get_default_tagger() -> BaseTagger:
    """
    Get the default tagger.
    
    Returns DGHS WD14 tagger if available, otherwise falls back to Camie V2 or Camie.
    
    Raises:
        ImportError: If no tagger backend is available.
    """
    if dghs.is_available():
        return dghs.DghsWD14Tagger()
    if camie_v2.is_available():
        return camie_v2.CamieV2Tagger()
    if camie.is_available():
        return camie.CamieTagger()
    raise ImportError(
        "No tagger backend available. Install:\n"
        "  pip install dghs-imgutils[gpu]  # Recommended (includes WD14, ML-Danbooru, Camie)\n"
        "  pip install transformers torch   # For Camie V2"
    )


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
