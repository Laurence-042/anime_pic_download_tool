#!/usr/bin/env python
"""
Hydrus Sidecar Tagger - Integrated post-processor for generating Hydrus-compatible JSON sidecars.

This module provides functionality to:
1. Detect and rename ComfyUI generated images (add .comfy suffix)
2. Extract tags from images using dghs-imgutils (WD14/ML-Danbooru models)
3. Infer source URLs from filenames
4. Handle animated images (gif/apng) by using static frames (jpg/png) for tagging
5. Export tags and URLs in Hydrus sidecar JSON format

Usage:
    # As a post-processor for newly downloaded files
    from hydrus_tagger import post_process_file
    final_path = post_process_file("./download/image.png")
    
    # As a batch processor for existing files
    python hydrus_tagger.py ./download --recursive
    python hydrus_tagger.py ./download --dry-run
    
    # Process a single file
    python hydrus_tagger.py ./download/image.png

Hydrus Sidecar Format:
    {
        "tags": ["tag1", "tag2", ...],
        "urls": ["https://..."]
    }

Supported filename patterns:
    - pixiv_{id}_p{index}.{ext}      -> https://www.pixiv.net/artworks/{id}
    - twitter_{author}_{id}_{index}.{ext} -> https://x.com/{author}/status/{id}
    - danbooru_{id}_{artist}_{source}.{ext} -> https://danbooru.donmai.us/posts/{id}
    - gelbooru_{id}_{artist}_{source}.{ext} -> https://gelbooru.com/index.php?page=post&s=view&id={id}
    - yandere_{id}_{artist}_{source}.{ext} -> https://yande.re/post/show/{id}
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from PIL import Image

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup NVIDIA CUDA paths before importing anything that uses onnxruntime
from utils import setup_nvidia_cuda_path
setup_nvidia_cuda_path()

# Import utility functions
from utils import (
    is_comfy_image,
    get_comfy_filename,
    infer_url_from_filename,
    find_static_version,
    ALL_IMAGE_EXTENSIONS,
    STATIC_IMAGE_EXTENSIONS,
    ANIMATED_IMAGE_EXTENSIONS,
)

# Sidecar file suffix
SIDECAR_SUFFIX = ".json"


@dataclass
class ProcessResult:
    """Result of processing an image file."""
    original_path: str
    final_path: str
    sidecar_path: str
    tags: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    is_comfyui: bool = False
    was_renamed: bool = False
    used_static_for_animated: bool = False
    success: bool = True
    error: Optional[str] = None


def rename_comfy_image(file_path: str, dry_run: bool = False) -> Tuple[str, bool]:
    """
    Rename ComfyUI image with .comfy suffix if detected.
    
    Returns:
        Tuple of (final_path, was_renamed)
    """
    if not os.path.exists(file_path):
        return file_path, False
    
    if '.comfy.' in file_path.lower():
        return file_path, False
    
    if not is_comfy_image(file_path):
        return file_path, False
    
    new_path = get_comfy_filename(file_path)
    
    if dry_run:
        return new_path, True
    
    try:
        os.rename(file_path, new_path)
        return new_path, True
    except Exception as e:
        print(f"Error renaming {file_path}: {e}")
        return file_path, False


def get_sidecar_path(image_path: str) -> str:
    """
    Generate the sidecar JSON file path for an image.
    Example: image.png -> image.png.json
    """
    return f"{image_path}{SIDECAR_SUFFIX}"


def load_existing_sidecar(sidecar_path: str) -> Dict:
    """Load existing sidecar data if it exists."""
    if os.path.exists(sidecar_path):
        try:
            with open(sidecar_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_sidecar(sidecar_path: str, data: Dict) -> None:
    """Save sidecar data to JSON file."""
    with open(sidecar_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_image_tags(image_path: str, threshold: float = 0.35, 
                   character_threshold: float = 0.85) -> Tuple[List[str], Optional[str]]:
    """
    Extract tags from an image using both WD14 EVA02_Large and Camie V2.
    Returns the union of tags from both models.
    """
    all_tags = set()
    rating = None
    
    # Step 1: Run WD14 EVA02_Large with threshold 0.52
    try:
        from tagger import dghs
        
        if dghs.is_available():
            tagger = dghs.DghsWD14Tagger(model_name='EVA02_Large')
            result = tagger.get_tags(image_path, threshold=0.52, character_threshold=character_threshold)
            
            wd14_tags = set(result.tags.keys())
            all_tags.update(wd14_tags)
            
            # Extract rating from WD14 results
            rating_tags = [t for t in wd14_tags if t.startswith('rating:')]
            if rating_tags:
                rating = rating_tags[0].split(':', 1)[1]
            
            print(f"  WD14 EVA02-Large: {len(wd14_tags)} tags")
        else:
            print(f"  Warning: dghs-imgutils not available, skipping WD14")
            
    except ImportError as e:
        print(f"  Warning: Could not import dghs tagger: {e}")
    except Exception as e:
        print(f"  Warning: Error running WD14 on {image_path}: {e}")
    
    # Step 2: Run Camie V2 with threshold 0.51
    try:
        from tagger.camie_v2 import CamieV2Tagger
        
        camie_tagger = CamieV2Tagger()
        result = camie_tagger.get_tags(image_path, threshold=0.51, character_threshold=character_threshold)
        
        # Add namespace prefixes based on tag category
        camie_tags_with_namespace = set()
        for tag in result.tags.keys():
            category = camie_tagger._tag_to_category.get(tag, 'general')
            
            if category == 'artist':
                prefixed_tag = f'creator:{tag}'
            elif category == 'character':
                prefixed_tag = f'character:{tag}'
            elif category == 'copyright':
                prefixed_tag = f'series:{tag}'
            else:
                # general, meta tags - no prefix
                prefixed_tag = tag
            
            camie_tags_with_namespace.add(prefixed_tag)
        
        all_tags.update(camie_tags_with_namespace)
        
        print(f"  Camie V2: {len(result.tags)} tags")
        
    except ImportError as e:
        print(f"  Warning: Could not import Camie V2 tagger: {e}")
    except Exception as e:
        print(f"  Warning: Error running Camie V2 on {image_path}: {e}")
    
    return list(all_tags), rating


def process_image(
    file_path: str,
    threshold: float = 0.35,
    character_threshold: float = 0.85,
    dry_run: bool = False,
    skip_existing: bool = False,
) -> ProcessResult:
    """
    Process a single image file:
    1. Rename if ComfyUI detected
    2. Extract tags
    3. Infer URL from filename
    4. Generate Hydrus sidecar JSON
    """
    file_path = os.path.abspath(file_path)
    original_path = file_path
    
    # Check if file exists
    if not os.path.exists(file_path):
        return ProcessResult(
            original_path=original_path,
            final_path=file_path,
            sidecar_path="",
            success=False,
            error="File not found"
        )
    
    # Step 1: Rename ComfyUI images
    final_path, was_renamed = rename_comfy_image(file_path, dry_run)
    is_comfyui = was_renamed or '.comfy.' in file_path.lower()
    
    # Update file_path to the renamed path (for non-dry-run)
    if was_renamed and not dry_run:
        file_path = final_path
    
    sidecar_path = get_sidecar_path(final_path)
    
    # Check if sidecar already exists
    if skip_existing and os.path.exists(sidecar_path):
        return ProcessResult(
            original_path=original_path,
            final_path=final_path,
            sidecar_path=sidecar_path,
            is_comfyui=is_comfyui,
            was_renamed=was_renamed,
            success=True,
            error="Skipped: sidecar exists"
        )
    
    # Step 2: Determine which image to use for tagging
    ext = Path(file_path).suffix.lower()
    tagging_image_path = file_path if not dry_run or not was_renamed else original_path
    used_static_for_animated = False
    
    if ext in ANIMATED_IMAGE_EXTENSIONS:
        static_path = find_static_version(tagging_image_path)
        if static_path:
            tagging_image_path = static_path
            used_static_for_animated = True
    
    # Step 3: Extract tags
    tags, rating = get_image_tags(tagging_image_path, threshold, character_threshold)
    
    # Add comfyui tag if detected
    if is_comfyui and 'comfyui' not in tags:
        tags.append('comfyui')
    
    # Add rating as tag
    if rating:
        rating_tag = f"rating:{rating}"
        if rating_tag not in tags:
            tags.append(rating_tag)
    
    # Step 4: Infer URL from filename
    filename = os.path.basename(final_path)
    url = infer_url_from_filename(filename)
    urls = [url] if url else []
    
    if dry_run:
        return ProcessResult(
            original_path=original_path,
            final_path=final_path,
            sidecar_path=sidecar_path,
            tags=tags,
            urls=urls,
            is_comfyui=is_comfyui,
            was_renamed=was_renamed,
            used_static_for_animated=used_static_for_animated,
            success=True,
            error="Dry run - not saved"
        )
    
    # Step 5: Load existing sidecar and merge
    existing_data = load_existing_sidecar(sidecar_path)
    
    # Merge tags
    existing_tags = set(existing_data.get('tags', []))
    all_tags = list(existing_tags | set(tags))
    
    # Merge URLs
    existing_urls = set(existing_data.get('urls', []))
    all_urls = list(existing_urls | set(urls))
    
    # Create sidecar data in Hydrus format
    sidecar_data = {
        "tags": all_tags,
        "urls": all_urls
    }
    
    try:
        save_sidecar(sidecar_path, sidecar_data)
        return ProcessResult(
            original_path=original_path,
            final_path=final_path,
            sidecar_path=sidecar_path,
            tags=all_tags,
            urls=all_urls,
            is_comfyui=is_comfyui,
            was_renamed=was_renamed,
            used_static_for_animated=used_static_for_animated,
            success=True
        )
    except Exception as e:
        return ProcessResult(
            original_path=original_path,
            final_path=final_path,
            sidecar_path=sidecar_path,
            tags=tags,
            urls=urls,
            is_comfyui=is_comfyui,
            was_renamed=was_renamed,
            used_static_for_animated=used_static_for_animated,
            success=False,
            error=str(e)
        )


def process_directory(
    directory: str,
    recursive: bool = True,
    dry_run: bool = False,
    skip_existing: bool = False,
    threshold: float = 0.35,
    character_threshold: float = 0.85,
) -> Dict:
    """
    Process all image files in a directory.
    """
    stats = {
        'total': 0,
        'processed': 0,
        'renamed': 0,
        'comfyui': 0,
        'skipped': 0,
        'errors': 0,
        'animated_with_static': 0,
        'urls_inferred': 0,
    }
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        return stats
    
    # Collect image files
    if recursive:
        file_iterator = (
            os.path.join(root, file)
            for root, dirs, files in os.walk(directory)
            for file in files
        )
    else:
        file_iterator = (
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        )
    
    # Filter to image files only
    image_files = [
        f for f in file_iterator 
        if Path(f).suffix.lower() in ALL_IMAGE_EXTENSIONS
    ]
    
    stats['total'] = len(image_files)
    
    for file_path in image_files:
        print(f"Processing: {os.path.basename(file_path)}")
        
        result = process_image(
            file_path,
            threshold=threshold,
            character_threshold=character_threshold,
            dry_run=dry_run,
            skip_existing=skip_existing,
        )
        
        if result.success:
            if result.error and "Skipped" in result.error:
                stats['skipped'] += 1
                print(f"  Skipped (sidecar exists)")
            else:
                stats['processed'] += 1
                if result.was_renamed:
                    stats['renamed'] += 1
                    print(f"  Renamed: {os.path.basename(result.final_path)}")
                if result.is_comfyui:
                    stats['comfyui'] += 1
                if result.used_static_for_animated:
                    stats['animated_with_static'] += 1
                    print(f"  Used static version for tagging")
                if result.urls:
                    stats['urls_inferred'] += 1
                print(f"  Tags: {len(result.tags)}, URLs: {len(result.urls)}")
                if not dry_run:
                    print(f"  Sidecar: {os.path.basename(result.sidecar_path)}")
        else:
            stats['errors'] += 1
            print(f"  Error: {result.error}")
    
    return stats


def post_process_file(file_path: str, threshold: float = 0.35,
                      character_threshold: float = 0.85) -> str:
    """
    Post-process a newly downloaded file.
    This function is called by the downloader after each file is saved.
    
    Args:
        file_path: Path to the downloaded file
        threshold: Confidence threshold for general tags
        character_threshold: Confidence threshold for character tags
        
    Returns:
        The final file path (may be renamed if ComfyUI detected)
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ALL_IMAGE_EXTENSIONS:
        return file_path
    
    result = process_image(file_path, threshold, character_threshold)
    
    if result.success:
        if result.was_renamed:
            print(f"Renamed to: {os.path.basename(result.final_path)}")
        print(f"Generated sidecar: {os.path.basename(result.sidecar_path)}")
        print(f"  Tags: {len(result.tags)}, URLs: {len(result.urls)}")
        if not result.urls:
            print(f"\033[31m  Warning: Could not infer URL from filename\033[0m")
        if result.is_comfyui:
            print(f"  ComfyUI image detected")
    else:
        print(f"Failed to process: {result.error}")
    
    return result.final_path


# Backward compatibility alias
process_downloaded_file = post_process_file


def main():
    parser = argparse.ArgumentParser(
        description='Generate Hydrus-compatible JSON sidecars with image tags and URLs.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s ./download                     # Process download folder recursively
    %(prog)s ./download --dry-run           # Preview without saving
    %(prog)s ./download --skip-existing     # Skip files with existing sidecars
    %(prog)s ./download --no-recursive      # Only scan top-level directory
    %(prog)s ./download/image.png           # Process a single file
    %(prog)s ./download --threshold 0.5     # Use higher confidence threshold

Features:
    - Detects and renames ComfyUI images (adds .comfy suffix)
    - Extracts tags using WD14 tagger (GPU accelerated if available)
    - Infers source URLs from filenames (pixiv, twitter, danbooru, etc.)
    - For animated images, uses static version for tagging if available

Hydrus Sidecar Format:
    {
        "tags": ["tag1", "tag2", "comfyui", "rating:safe", ...],
        "urls": ["https://www.pixiv.net/artworks/12345"]
    }
        """
    )
    
    parser.add_argument(
        'path',
        help='Directory or file to process'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        dest='recursive',
        help='Scan subdirectories (default: True)'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_false',
        dest='recursive',
        help='Only scan the specified directory, not subdirectories'
    )
    
    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        default=False,
        help='Only show what would be done without saving'
    )
    
    parser.add_argument(
        '-s', '--skip-existing',
        action='store_true',
        default=False,
        help='Skip files that already have sidecar files'
    )
    
    parser.add_argument(
        '-t', '--threshold',
        type=float,
        default=0.35,
        help='Confidence threshold for general tags (default: 0.35)'
    )
    
    parser.add_argument(
        '-c', '--character-threshold',
        type=float,
        default=0.85,
        help='Confidence threshold for character tags (default: 0.85)'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)
    
    path = os.path.abspath(args.path)
    
    if os.path.isfile(path):
        print(f"Processing file: {path}")
        print(f"Dry run: {args.dry_run}")
        print("-" * 50)
        
        result = process_image(
            path,
            threshold=args.threshold,
            character_threshold=args.character_threshold,
            dry_run=args.dry_run,
        )
        
        print(f"Original: {result.original_path}")
        if result.was_renamed:
            print(f"Renamed to: {result.final_path}")
        print(f"Sidecar: {result.sidecar_path}")
        print(f"Tags ({len(result.tags)}): {', '.join(result.tags[:10])}{'...' if len(result.tags) > 10 else ''}")
        print(f"URLs: {result.urls}")
        print(f"ComfyUI: {result.is_comfyui}")
        print(f"Success: {result.success}")
        if result.error:
            print(f"Note: {result.error}")
    else:
        print(f"Processing directory: {path}")
        print(f"Recursive: {args.recursive}")
        print(f"Dry run: {args.dry_run}")
        print(f"Skip existing: {args.skip_existing}")
        print(f"Threshold: {args.threshold}")
        print(f"Character threshold: {args.character_threshold}")
        print("-" * 50)
        
        stats = process_directory(
            path,
            recursive=args.recursive,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            threshold=args.threshold,
            character_threshold=args.character_threshold,
        )
        
        print("-" * 50)
        print("Summary:")
        print(f"  Total image files:         {stats['total']}")
        print(f"  Successfully processed:    {stats['processed']}")
        print(f"  ComfyUI renamed:           {stats['renamed']}")
        print(f"  ComfyUI detected:          {stats['comfyui']}")
        print(f"  URLs inferred:             {stats['urls_inferred']}")
        print(f"  Skipped (existing):        {stats['skipped']}")
        print(f"  Animated with static ver:  {stats['animated_with_static']}")
        if stats['errors'] > 0:
            print(f"  Errors:                    {stats['errors']}")
        
        if args.dry_run and stats['processed'] > 0:
            print(f"\nRun without --dry-run to actually process {stats['processed']} file(s).")


if __name__ == '__main__':
    main()
