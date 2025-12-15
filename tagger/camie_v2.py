"""
Camie Tagger V2 implementation using custom model loading.

Direct implementation of Camais03/camie-tagger-v2 model with improved tag distribution.
This model uses a Vision Transformer backbone with custom architecture.

Model: https://huggingface.co/Camais03/camie-tagger-v2

Installation:
    # GPU version (recommended, requires NVIDIA GPU with CUDA)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install pillow safetensors huggingface-hub
    
    Note: This model requires custom loading code, not standard transformers.
    See CAMIE_V2_INSTALL.md for detailed instructions.
"""

from typing import Dict, Union, Optional
from PIL import Image
import numpy as np
import json
import os

from .base import BaseTagger, TagResult


# Try to import required libraries
try:
    import torch
    from safetensors.torch import load_file
    from huggingface_hub import hf_hub_download
    CAMIE_V2_AVAILABLE = True
except ImportError:
    CAMIE_V2_AVAILABLE = False


DEFAULT_THRESHOLD = 0.35
MODEL_REPO = "Camais03/camie-tagger-v2"

# Singleton instances to avoid reloading model
_model_session = None
_model_metadata = None

_model_idx_to_tag = None
_model_tag_to_category = None
_model_total_tags = None


class CamieV2Tagger(BaseTagger):
    """
    Camie V2 Tagger with improved tag distribution.
    
    Uses Camais03/camie-tagger-v2 directly with custom loading.
    Provides better tag distribution compared to v1/initial version.
    
    Note: This implementation uses ONNX model for simplicity.
    For full PyTorch model, see the original repo.
    """
    
    def __init__(self):
        """Initialize Camie V2 Tagger."""
        if not CAMIE_V2_AVAILABLE:
            raise ImportError(
                "Required packages are not installed.\n"
                "For GPU support (recommended):\n"
                "  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128\n"
                "  pip install pillow safetensors huggingface-hub\n"
                "\n"
                "See CAMIE_V2_INSTALL.md for detailed instructions."
            )
        
        # Use singleton instances
        global _model_session, _model_metadata, _model_idx_to_tag, _model_tag_to_category, _model_total_tags
        self._session = _model_session
        self._metadata = _model_metadata
        self._idx_to_tag = _model_idx_to_tag
        self._tag_to_category = _model_tag_to_category
        self._total_tags = _model_total_tags
    
    def _load_model(self):
        """Lazy load ONNX model on first use."""
        global _model_session, _model_metadata, _model_idx_to_tag, _model_tag_to_category, _model_total_tags
        
        if self._session is None:
            try:
                import onnxruntime as ort
            except ImportError:
                raise ImportError(
                    "onnxruntime is required but not installed.\n"
                    "Install with: pip install onnxruntime-gpu\n"
                    "or: pip install onnxruntime (CPU only)"
                )
            
            print(f"Loading {MODEL_REPO} ONNX model...")
            
            # Check for local files first
            local_model_dir = os.path.join(os.path.dirname(__file__), "..", "models", "camie-v2")
            local_model_path = os.path.join(local_model_dir, "camie-tagger-v2.onnx")
            local_metadata_path = os.path.join(local_model_dir, "camie-tagger-v2-metadata.json")
            
            if os.path.exists(local_model_path) and os.path.exists(local_metadata_path):
                print(f"Using local model files from: {local_model_dir}")
                model_path = local_model_path
                metadata_path = local_metadata_path
            else:
                print("Downloading model from HuggingFace...")
                print("If download is slow, you can manually download these files:")
                print("  1. https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2.onnx")
                print("  2. https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2-metadata.json")
                print(f"  Place them in: {local_model_dir}")
                
                # Download from HuggingFace
                model_path = hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename="camie-tagger-v2.onnx",
                    cache_dir=None  # Use default cache
                )
                
                metadata_path = hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename="camie-tagger-v2-metadata.json",
                    cache_dir=None
                )
            
            # Load metadata
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata_json = json.load(f)
            
            # Extract tag mappings from nested structure
            dataset_info = metadata_json['dataset_info']
            tag_mapping = dataset_info['tag_mapping']
            self._idx_to_tag = tag_mapping['idx_to_tag']  # Dict[str, str] - index to tag name
            self._tag_to_category = tag_mapping['tag_to_category']  # Dict[str, str] - tag to category
            self._total_tags = dataset_info['total_tags']
            self._metadata = metadata_json
            
            # Create ONNX session with optimized settings
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
            sess_options.log_severity_level = 3  # Only show errors (suppress warnings)
            
            # Configure CUDA provider for better performance
            cuda_options = {
                'arena_extend_strategy': 'kNextPowerOfTwo',
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            }
            
            providers = [
                ('CUDAExecutionProvider', cuda_options),
                'CPUExecutionProvider'
            ]
            
            self._session = ort.InferenceSession(
                model_path,
                sess_options=sess_options,
                providers=providers
            )
            
            # Update singleton
            _model_session = self._session
            _model_metadata = self._metadata
            _model_idx_to_tag = self._idx_to_tag
            _model_tag_to_category = self._tag_to_category
            _model_total_tags = self._total_tags
            
            device = self._session.get_providers()[0]
            print(f"Model loaded with {device}")
            print(f"Total tags: {self._total_tags}")
            print(f"Model expects input: {self._session.get_inputs()[0].name}, shape: {self._session.get_inputs()[0].shape}")
            print(f"Model outputs: {[o.name for o in self._session.get_outputs()]}")
    
    def get_tags(
        self,
        image: Union[str, Image.Image],
        threshold: float = DEFAULT_THRESHOLD,
        character_threshold: float = 0.85,
    ) -> TagResult:
        """
        Get tags for an image using Camie V2 model.
        
        Args:
            image: Path to image file or PIL Image object
            threshold: Confidence threshold for general tags
            character_threshold: Confidence threshold for character tags
            
        Returns:
            TagResult object containing tags and metadata
        """
        self._load_model()
        
        img = self._load_image(image)
        
        # Resize to 512x512 (model input size)
        img = img.convert('RGB')
        img = img.resize((512, 512), Image.Resampling.LANCZOS)
        
        # Convert to numpy array and normalize
        img_array = np.array(img).astype(np.float32) / 255.0
        
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
        img_array = ((img_array - mean) / std).astype(np.float32)
        
        # Convert to CHW format and add batch dimension
        img_array = img_array.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
        
        # Run inference
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: img_array})
        
        # Model has 3 outputs: initial_predictions, refined_predictions, selected_candidates
        # Use refined_predictions (output[1]) as recommended
        if len(outputs) >= 2:
            logits = outputs[1][0]  # refined_predictions, first batch item
        else:
            logits = outputs[0][0]  # fallback to first output
        
        # Apply sigmoid to convert logits to probabilities
        # Clip to prevent overflow in exp
        logits = np.clip(logits, -20, 20)
        probs = 1.0 / (1.0 + np.exp(-logits))
        
        # Create tags dictionary using metadata
        all_tags = {}
        general_tags = {}
        character_tags = {}
        
        # Process predictions
        for idx, prob in enumerate(probs):
            # Convert index to string for lookup
            idx_str = str(idx)
            
            # Get tag name from mapping
            tag_name = self._idx_to_tag.get(idx_str)
            if tag_name is None:
                continue  # Skip unknown indices
            
            # Get category for this tag
            category = self._tag_to_category.get(tag_name, 'general')
            
            # Skip rating tags
            if category == 'rating':
                continue
            
            # Convert to Python float
            prob = float(prob)
            
            # Separate character tags with different threshold
            if category == 'character':
                if prob >= character_threshold:
                    character_tags[tag_name] = prob
                    all_tags[tag_name] = prob
            else:
                if prob >= threshold:
                    general_tags[tag_name] = prob
                    all_tags[tag_name] = prob
        
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
        return ["v2"]
    
    def get_current_model(self) -> str:
        """Get the current model name."""
        return "v2"


def is_available() -> bool:
    """Check if required packages are available."""
    return CAMIE_V2_AVAILABLE


def get_tags(
    image: Union[str, Image.Image],
    threshold: float = DEFAULT_THRESHOLD,
    character_threshold: float = 0.85,
) -> TagResult:
    """
    Convenience function to get tags using Camie V2 tagger.
    
    Args:
        image: Path to image file or PIL Image object
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        TagResult object containing tags and metadata
    """
    tagger = CamieV2Tagger()
    return tagger.get_tags(image, threshold, character_threshold)
