"""
DeepGHS (dghs-imgutils) Tagger implementation.

This tagger uses the dghs-imgutils library which provides access to:
- WD14 Tagger v3 models (SmilingWolf)
- ML-Danbooru (12,547 tags, Caformer architecture)
- And many other anime-related image processing tools

Installation:
    pip install dghs-imgutils[gpu]  # For GPU support
    pip install dghs-imgutils       # CPU only

Available models:
- WD14: EVA02_Large, ViT_Large, ViT, SwinV2, ConvNext, etc.
- ML-Danbooru: Caformer-based model with 12,547 tags

Documentation: https://deepghs.github.io/imgutils/
"""

from typing import List, Dict, Union
from PIL import Image

from .base import BaseTagger, TagResult


# Try to import dghs-imgutils
try:
    from imgutils.tagging import get_wd14_tags, get_mldanbooru_tags
    DGHS_AVAILABLE = True
except ImportError:
    DGHS_AVAILABLE = False


# WD14 model names available in dghs-imgutils
WD14_MODELS = [
    "EVA02_Large",  # Best accuracy
    "ViT_Large",
    "ViT",
    "SwinV2",
    "ConvNext",
    "MOAT",
    "ConvNextV2",
]

DEFAULT_MODEL = "EVA02_Large"
DEFAULT_THRESHOLD = 0.35
DEFAULT_CHARACTER_THRESHOLD = 0.85


class DghsWD14Tagger(BaseTagger):
    """
    WD14 Tagger using dghs-imgutils library.
    
    This provides the same WD14 models but with the maintained dghs-imgutils wrapper.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize DGHS WD14 Tagger.
        
        Args:
            model_name: Name of the WD14 model to use (EVA02_Large, ViT_Large, etc.)
        """
        if not DGHS_AVAILABLE:
            raise ImportError(
                "dghs-imgutils is not installed. "
                "Install with: pip install dghs-imgutils[gpu] or pip install dghs-imgutils"
            )
        self.model_name = model_name
    
    def get_tags(
        self,
        image: Union[str, Image.Image],
        threshold: float = DEFAULT_THRESHOLD,
        character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
    ) -> TagResult:
        """
        Get tags for an image using WD14 model.
        
        Args:
            image: Path to image file or PIL Image object
            threshold: Confidence threshold for general tags
            character_threshold: Confidence threshold for character tags
            
        Returns:
            TagResult object containing tags and metadata
        """
        img = self._load_image(image)
        
        # Call dghs-imgutils WD14 tagger
        rating, features, chars = get_wd14_tags(
            img,
            model_name=self.model_name,
            general_threshold=threshold,
            character_threshold=character_threshold,
        )
        
        # Determine rating
        rating_str = max(rating.items(), key=lambda x: x[1])[0] if rating else None
        
        # Combine all tags
        all_tags = {**chars, **features}
        
        # Create raw string
        sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
        raw_string = ", ".join(
            tag.replace("(", "\\(").replace(")", "\\)")
            for tag, _ in sorted_tags
        )
        
        return TagResult(
            tags=all_tags,
            character_tags=chars,
            general_tags=features,
            rating=rating_str,
            raw_string=raw_string,
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of available WD14 models."""
        return WD14_MODELS.copy()
    
    def get_current_model(self) -> str:
        """Get the current model name."""
        return self.model_name


class DghsMLDanbooruTagger(BaseTagger):
    """
    ML-Danbooru Tagger using dghs-imgutils library.
    
    ML-Danbooru has 12,547 tags and uses Caformer architecture.
    It provides more comprehensive tagging than WD14 models.
    """
    
    def __init__(self):
        """Initialize ML-Danbooru Tagger."""
        if not DGHS_AVAILABLE:
            raise ImportError(
                "dghs-imgutils is not installed. "
                "Install with: pip install dghs-imgutils[gpu] or pip install dghs-imgutils"
            )
        self._model_name = "ml-danbooru"
    
    def get_tags(
        self,
        image: Union[str, Image.Image],
        threshold: float = DEFAULT_THRESHOLD,
        character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,  # Not used, for interface compatibility
    ) -> TagResult:
        """
        Get tags for an image using ML-Danbooru model.
        
        Args:
            image: Path to image file or PIL Image object
            threshold: Confidence threshold for tags
            character_threshold: Not used (ML-Danbooru doesn't separate character tags)
            
        Returns:
            TagResult object containing tags and metadata
        """
        img = self._load_image(image)
        
        # Call dghs-imgutils ML-Danbooru tagger
        tags = get_mldanbooru_tags(img, threshold=threshold)
        
        # ML-Danbooru returns a dict of tag: score
        # It doesn't separate character/general tags
        all_tags = dict(tags)
        
        # Create raw string
        sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
        raw_string = ", ".join(
            tag.replace("(", "\\(").replace(")", "\\)")
            for tag, _ in sorted_tags
        )
        
        return TagResult(
            tags=all_tags,
            character_tags={},  # ML-Danbooru doesn't separate
            general_tags=all_tags,
            raw_string=raw_string,
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of available models (only one for ML-Danbooru)."""
        return ["ml-danbooru"]
    
    def get_current_model(self) -> str:
        """Get the current model name."""
        return self._model_name


# Convenience functions
def get_tags(
    image: Union[str, Image.Image],
    model: str = "wd14",
    threshold: float = DEFAULT_THRESHOLD,
    character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
) -> TagResult:
    """
    Convenience function to get tags using dghs-imgutils.
    
    Args:
        image: Path to image file or PIL Image object
        model: Model to use ("wd14" or "mldanbooru")
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        TagResult object containing tags and metadata
    """
    if model.lower() in ["wd14", "wd"]:
        tagger = DghsWD14Tagger()
    elif model.lower() in ["mldanbooru", "ml-danbooru", "danbooru"]:
        tagger = DghsMLDanbooruTagger()
    else:
        # Assume it's a WD14 model name
        tagger = DghsWD14Tagger(model_name=model)
    
    return tagger.get_tags(image, threshold, character_threshold)


def is_available() -> bool:
    """Check if dghs-imgutils is available."""
    return DGHS_AVAILABLE
