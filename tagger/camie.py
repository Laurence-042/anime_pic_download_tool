"""
Camie Tagger implementation using dghs-imgutils.

Camie Tagger can identify 70,000+ tags including rating, general, and character tags.
Based on Camais03/camie-tagger, using ONNX optimizations from deepghs/camie_tagger_onnx.

Original: https://huggingface.co/Camais03/camie-tagger
ONNX: https://huggingface.co/deepghs/camie_tagger_onnx

Installation:
    pip install dghs-imgutils[gpu]  # For GPU support
    pip install dghs-imgutils       # CPU only

Documentation: https://dghs-imgutils.deepghs.org/main/api_doc/tagging/camie.html
"""

from typing import Dict, Union
from PIL import Image

from .base import BaseTagger, TagResult


# Try to import dghs-imgutils
try:
    from imgutils.tagging import get_camie_tags
    CAMIE_AVAILABLE = True
except ImportError:
    CAMIE_AVAILABLE = False


DEFAULT_THRESHOLD = 0.35


class CamieTagger(BaseTagger):
    """
    Camie Tagger supporting 70,000+ tags.
    
    Supports rating, general tags, and character tags.
    Uses high_recall mode by default for better coverage.
    Note: dghs-imgutils uses deepghs/camie_tagger_onnx, not the original Camais03 models.
    """
    
    def __init__(self, model_name: str = 'initial', mode: str = 'high_recall'):
        """
        Initialize Camie Tagger.
        
        Args:
            model_name: Name of the Camie model to use (default: 'initial')
                       Note: dghs-imgutils may only support 'initial' model
            mode: Prediction mode affecting threshold values:
                  - 'balanced': Balanced precision/recall
                  - 'high_precision': Higher precision thresholds
                  - 'high_recall': Higher recall thresholds
                  - 'micro_opt': Micro-optimized thresholds
                  - 'macro_opt': Macro-optimized thresholds
        """
        if not CAMIE_AVAILABLE:
            raise ImportError(
                "dghs-imgutils is not installed. "
                "Install with: pip install dghs-imgutils[gpu] or pip install dghs-imgutils"
            )
        self._model_name = model_name
        self._mode = mode
    
    def get_tags(
        self,
        image: Union[str, Image.Image],
        threshold: float = DEFAULT_THRESHOLD,
        character_threshold: float = 0.85,
    ) -> TagResult:
        """
        Get tags for an image using Camie model.
        
        Args:
            image: Path to image file or PIL Image object
            threshold: Confidence threshold for general tags
            character_threshold: Confidence threshold for character tags
            
        Returns:
            TagResult object containing tags and metadata
        """
        img = self._load_image(image)
        
        # Use dghs-imgutils Camie tagger
        # Returns: (rating_dict, general_dict, character_dict)
        rating, general, characters = get_camie_tags(
            img,
            model_name=self._model_name,
            mode=self._mode
        )
        
        # Filter general tags by threshold
        general_tags = {tag: score for tag, score in general.items() if score >= threshold}
        
        # Filter character tags by character_threshold
        character_tags = {tag: score for tag, score in characters.items() if score >= character_threshold}
        
        # Combine all tags (general + character)
        all_tags = {**general_tags, **character_tags}
        
        # Optionally add rating as a tag (use highest rated category)
        if rating:
            max_rating = max(rating.items(), key=lambda x: x[1])
            if max_rating[1] >= threshold:
                all_tags[f"rating:{max_rating[0]}"] = max_rating[1]
        
        # Create raw string (sorted by confidence)
        sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
        raw_string = ", ".join(
            tag.replace("(", "\\(").replace(")", "\\)")
            for tag, _ in sorted_tags
        )
        
        return TagResult(
            tags=all_tags,
            character_tags=character_tags,
            general_tags=general_tags,
            raw_string=raw_string,
        )
    
    def get_available_models(self) -> list:
        """Get list of available models."""
        # dghs-imgutils uses deepghs/camie_tagger_onnx which may only have 'initial'
        return ["initial"]
    
    def get_current_model(self) -> str:
        """Get the current model name."""
        return self._model_name


def is_available() -> bool:
    """Check if dghs-imgutils (Camie) is available."""
    return CAMIE_AVAILABLE


def get_tags(
    image: Union[str, Image.Image],
    threshold: float = DEFAULT_THRESHOLD,
    character_threshold: float = 0.85,
) -> TagResult:
    """
    Convenience function to get tags using Camie tagger.
    
    Args:
        image: Path to image file or PIL Image object
        threshold: Confidence threshold for tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        TagResult object containing tags and metadata
    """
    tagger = CamieTagger()
    return tagger.get_tags(image, threshold, character_threshold)
