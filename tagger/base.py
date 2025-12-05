"""
Base class for anime image taggers.

All tagger implementations should inherit from BaseTagger and implement the get_tags method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


@dataclass
class TagResult:
    """Result of tagging an image."""
    # All tags with confidence scores
    tags: Dict[str, float]
    # Character tags (if available)
    character_tags: Dict[str, float]
    # General tags (if available)  
    general_tags: Dict[str, float]
    # Rating (if available): safe, questionable, explicit
    rating: Optional[str] = None
    # Raw tags string (comma-separated)
    raw_string: str = ""
    
    def to_string(self, threshold: float = 0.0, separator: str = ", ") -> str:
        """Convert tags to comma-separated string."""
        filtered = [tag for tag, score in self.tags.items() if score >= threshold]
        return separator.join(filtered)
    
    def get_top_tags(self, n: int = 10) -> List[str]:
        """Get top N tags by confidence."""
        sorted_tags = sorted(self.tags.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in sorted_tags[:n]]


class BaseTagger(ABC):
    """Base class for all taggers."""
    
    @abstractmethod
    def get_tags(
        self,
        image,
        threshold: float = 0.35,
        character_threshold: float = 0.85,
    ) -> TagResult:
        """
        Get tags for an image.
        
        Args:
            image: Path to image file or PIL Image object
            threshold: Confidence threshold for general tags
            character_threshold: Confidence threshold for character tags
            
        Returns:
            TagResult object containing tags and metadata
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this tagger."""
        pass
    
    @abstractmethod
    def get_current_model(self) -> str:
        """Get the current model name."""
        pass
    
    def _load_image(self, image):
        """Load image from path or return as-is if already PIL Image."""
        from PIL import Image
        if isinstance(image, str):
            return Image.open(image)
        return image