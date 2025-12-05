# Portions of this code are from:
# ComfyUI-WD14-Tagger (MIT License)
# Copyright (c) 2023 pythongosssss
# Original source: https://github.com/pythongosssss/ComfyUI-WD14-Tagger
#
# This project is licensed under the MIT License.
# See LICENSE in the project root for license information.

"""
WD14 Tagger implementation using SmilingWolf's models.

Available models (v3 - 2024, recommended):
- wd-eva02-large-tagger-v3 (Best accuracy)
- wd-vit-large-tagger-v3
- wd-vit-tagger-v3
- wd-swinv2-tagger-v3
- wd-convnext-tagger-v3

Legacy models (v2 - 2023):
- wd-v1-4-moat-tagger-v2
- wd-v1-4-convnext-tagger-v2
- wd-v1-4-convnextv2-tagger-v2
- wd-v1-4-vit-tagger-v2
- wd-v1-4-swinv2-tagger-v2

Requirements:
    pip install onnxruntime  # CPU only
    pip install onnxruntime-gpu  # GPU support
"""

import asyncio
import csv
import os
from typing import List, Dict, Union

from .base import BaseTagger, TagResult

# Try to import optional dependencies
try:
    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    import aiohttp
    WD14_AVAILABLE = True
except ImportError:
    WD14_AVAILABLE = False

# Model configuration
MODELS = {
    # v3 models - Latest (2024) - Recommended
    "wd-eva02-large-tagger-v3": "https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3",
    "wd-vit-large-tagger-v3": "https://huggingface.co/SmilingWolf/wd-vit-large-tagger-v3",
    "wd-vit-tagger-v3": "https://huggingface.co/SmilingWolf/wd-vit-tagger-v3",
    "wd-swinv2-tagger-v3": "https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3",
    "wd-convnext-tagger-v3": "https://huggingface.co/SmilingWolf/wd-convnext-tagger-v3",
    # v2 models - Legacy (2023)
    "wd-v1-4-moat-tagger-v2": "https://huggingface.co/SmilingWolf/wd-v1-4-moat-tagger-v2",
    "wd-v1-4-convnext-tagger-v2": "https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2",
    "wd-v1-4-convnextv2-tagger-v2": "https://huggingface.co/SmilingWolf/wd-v1-4-convnextv2-tagger-v2",
    "wd-v1-4-vit-tagger-v2": "https://huggingface.co/SmilingWolf/wd-v1-4-vit-tagger-v2",
    "wd-v1-4-swinv2-tagger-v2": "https://huggingface.co/SmilingWolf/wd-v1-4-swinv2-tagger-v2",
}

DEFAULT_MODEL = "wd-eva02-large-tagger-v3"
DEFAULT_THRESHOLD = 0.35
DEFAULT_CHARACTER_THRESHOLD = 0.85

# Models directory - created lazily
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wd14_models")

# ORT providers
ORT_PROVIDERS = ["CUDAExecutionProvider", "CPUExecutionProvider"]


def is_available() -> bool:
    """Check if WD14 tagger dependencies are available."""
    return WD14_AVAILABLE


def _get_installed_models() -> List[str]:
    """Get list of installed models."""
    if not os.path.exists(MODELS_DIR):
        return []
    models = [f for f in os.listdir(MODELS_DIR) if f.endswith(".onnx")]
    models = [m for m in models if os.path.exists(os.path.join(MODELS_DIR, os.path.splitext(m)[0] + ".csv"))]
    return models


async def _download_model(model_name: str, hf_endpoint: str = None):
    """Download model from HuggingFace."""
    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODELS.keys())}")
    
    if hf_endpoint is None:
        hf_endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co")
    if not hf_endpoint.startswith("https://"):
        hf_endpoint = f"https://{hf_endpoint}"
    if hf_endpoint.endswith("/"):
        hf_endpoint = hf_endpoint.rstrip("/")
    
    base_url = MODELS[model_name].replace("https://huggingface.co", hf_endpoint)
    url = f"{base_url}/resolve/main/"
    
    # Ensure models directory exists
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
    
    onnx_path = os.path.join(MODELS_DIR, f"{model_name}.onnx")
    csv_path = os.path.join(MODELS_DIR, f"{model_name}.csv")
    
    async with aiohttp.ClientSession() as session:
        # Download ONNX model
        if not os.path.exists(onnx_path):
            print(f"Downloading {model_name}.onnx...")
            async with session.get(f"{url}model.onnx") as response:
                if response.status != 200:
                    raise Exception(f"Failed to download model: {response.status}")
                content = await response.read()
                with open(onnx_path, 'wb') as f:
                    f.write(content)
                print(f"Downloaded {model_name}.onnx")
        
        # Download CSV tags
        if not os.path.exists(csv_path):
            print(f"Downloading {model_name}.csv...")
            async with session.get(f"{url}selected_tags.csv") as response:
                if response.status != 200:
                    raise Exception(f"Failed to download tags: {response.status}")
                content = await response.read()
                with open(csv_path, 'wb') as f:
                    f.write(content)
                print(f"Downloaded {model_name}.csv")


class WD14Tagger(BaseTagger):
    """WD14 Tagger using SmilingWolf's models."""
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        hf_endpoint: str = None,
        replace_underscore: bool = True,
    ):
        """
        Initialize WD14 Tagger.
        
        Args:
            model_name: Name of the model to use
            hf_endpoint: HuggingFace endpoint (for mirrors)
            replace_underscore: Replace underscores with spaces in tags
        """
        if not WD14_AVAILABLE:
            raise ImportError(
                "WD14 tagger dependencies are not installed. "
                "Install with: pip install onnxruntime numpy pillow aiohttp"
            )
        if model_name.endswith(".onnx"):
            model_name = model_name[:-5]
        self.model_name = model_name
        self.hf_endpoint = hf_endpoint
        self.replace_underscore = replace_underscore
        self._model = None
        self._tags = None
        self._general_index = None
        self._character_index = None
    
    def _ensure_model(self):
        """Ensure model is downloaded and loaded."""
        if self._model is not None:
            return
        
        # Ensure models directory exists
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR)
        
        # Check if model is installed
        installed = _get_installed_models()
        if f"{self.model_name}.onnx" not in installed:
            asyncio.run(_download_model(self.model_name, self.hf_endpoint))
        
        # Load model
        model_path = os.path.join(MODELS_DIR, f"{self.model_name}.onnx")
        self._model = ort.InferenceSession(model_path, providers=ORT_PROVIDERS)
        
        # Load tags from CSV
        self._tags = []
        self._general_index = None
        self._character_index = None
        csv_path = os.path.join(MODELS_DIR, f"{self.model_name}.csv")
        
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if self._general_index is None and row[2] == "0":
                    self._general_index = reader.line_num - 2
                elif self._character_index is None and row[2] == "4":
                    self._character_index = reader.line_num - 2
                if self.replace_underscore:
                    self._tags.append(row[1].replace("_", " "))
                else:
                    self._tags.append(row[1])
    
    def get_tags(
        self,
        image,
        threshold: float = DEFAULT_THRESHOLD,
        character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
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
        self._ensure_model()
        
        # Load image
        img = self._load_image(image)
        
        # Get input size
        input_layer = self._model.get_inputs()[0]
        height = input_layer.shape[1]
        
        # Preprocess image: resize and pad with white
        ratio = float(height) / max(img.size)
        new_size = tuple([int(x * ratio) for x in img.size])
        img = img.resize(new_size, Image.LANCZOS)
        square = Image.new("RGB", (height, height), (255, 255, 255))
        square.paste(img, ((height - new_size[0]) // 2, (height - new_size[1]) // 2))
        
        # Convert to numpy array
        image_array = np.array(square).astype(np.float32)
        image_array = image_array[:, :, ::-1]  # RGB -> BGR
        image_array = np.expand_dims(image_array, 0)
        
        # Run inference
        label_name = self._model.get_outputs()[0].name
        probs = self._model.run([label_name], {input_layer.name: image_array})[0]
        
        result = list(zip(self._tags, probs[0]))
        
        # Separate by category
        general_results = {
            item[0]: float(item[1]) 
            for item in result[self._general_index:self._character_index] 
            if item[1] > threshold
        }
        character_results = {
            item[0]: float(item[1]) 
            for item in result[self._character_index:] 
            if item[1] > character_threshold
        }
        
        # Combine all tags
        all_tags = {**character_results, **general_results}
        
        # Create raw string
        sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
        raw_string = ", ".join(
            tag.replace("(", "\\(").replace(")", "\\)")
            for tag, _ in sorted_tags
        )
        
        return TagResult(
            tags=all_tags,
            character_tags=character_results,
            general_tags=general_results,
            raw_string=raw_string,
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return list(MODELS.keys())
    
    def get_current_model(self) -> str:
        """Get the current model name."""
        return self.model_name


# Convenience functions for backward compatibility
def get_tags(
    image: Union[str, "Image.Image"],
    model_name: str = DEFAULT_MODEL,
    threshold: float = DEFAULT_THRESHOLD,
    character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
) -> TagResult:
    """
    Convenience function to get tags for an image.
    
    Args:
        image: Path to image file or PIL Image object
        model_name: Name of the model to use
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        TagResult object containing tags and metadata
    """
    tagger = WD14Tagger(model_name=model_name)
    return tagger.get_tags(image, threshold, character_threshold)


def get_tags_string(
    image: Union[str, "Image.Image"],
    model_name: str = DEFAULT_MODEL,
    threshold: float = DEFAULT_THRESHOLD,
    character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
) -> str:
    """
    Convenience function to get tags as a comma-separated string.
    
    Args:
        image: Path to image file or PIL Image object
        model_name: Name of the model to use
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        Comma-separated string of tags
    """
    result = get_tags(image, model_name, threshold, character_threshold)
    return result.raw_string
