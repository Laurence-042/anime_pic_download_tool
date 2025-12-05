#!/usr/bin/env python
"""
Tag Analyzer - Analyze tag patterns from Hydrus sidecar JSON files using FP-Growth.

This script reads all sidecar JSON files from a directory, collects tag sets,
and uses FP-Growth algorithm to find frequent itemsets (tag combinations).

Usage:
    python tag_analyzer.py ./download                    # Analyze tags in download folder
    python tag_analyzer.py ./download --min-support 0.1  # Set minimum support threshold
    python tag_analyzer.py ./download --min-items 2      # Only show itemsets with 2+ tags
    python tag_analyzer.py ./download --max-items 5      # Only show itemsets with up to 5 tags
    python tag_analyzer.py ./download --top 50           # Show top 50 frequent itemsets
    python tag_analyzer.py ./download --exclude-rating   # Exclude rating:* tags
    python tag_analyzer.py ./download -o result.json     # Export results to JSON

Output:
    Displays frequent tag combinations sorted by support (frequency).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """Result of tag analysis."""
    total_files: int = 0
    total_tags: int = 0
    unique_tags: int = 0
    tag_sets: List[Set[str]] = field(default_factory=list)
    tag_frequency: Dict[str, int] = field(default_factory=dict)
    frequent_itemsets: List[Tuple[frozenset, float]] = field(default_factory=list)


def collect_tag_sets(
    directory: str,
    recursive: bool = True,
    exclude_patterns: List[str] = None
) -> Tuple[List[Set[str]], Counter]:
    """
    Collect all tag sets from sidecar JSON files in a directory.
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        exclude_patterns: Tag prefixes to exclude (e.g., ['rating:'])
        
    Returns:
        Tuple of (list of tag sets, tag frequency counter)
    """
    tag_sets = []
    tag_counter = Counter()
    exclude_patterns = exclude_patterns or []
    
    if recursive:
        json_files = Path(directory).rglob("*.json")
    else:
        json_files = Path(directory).glob("*.json")
    
    for json_path in json_files:
        # Skip non-sidecar JSON files (sidecar files end with .png.json, .jpg.json, etc.)
        if not any(str(json_path).lower().endswith(f"{ext}.json") 
                   for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.apng', '.bmp']):
            continue
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            tags = data.get('tags', [])
            if not tags:
                continue
            
            # Filter out excluded patterns
            filtered_tags = set()
            for tag in tags:
                if not any(tag.startswith(pattern) for pattern in exclude_patterns):
                    filtered_tags.add(tag)
            
            if filtered_tags:
                tag_sets.append(filtered_tags)
                tag_counter.update(filtered_tags)
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_path}: {e}")
            continue
    
    return tag_sets, tag_counter


def fp_growth(
    tag_sets: List[Set[str]],
    min_support: float = 0.05,
    min_items: int = 1,
    max_items: int = None
) -> List[Tuple[frozenset, float]]:
    """
    Find frequent itemsets using FP-Growth algorithm.
    
    Args:
        tag_sets: List of tag sets
        min_support: Minimum support threshold (0.0 to 1.0)
        min_items: Minimum number of items in an itemset
        max_items: Maximum number of items in an itemset (None for no limit)
        
    Returns:
        List of (itemset, support) tuples sorted by support descending
    """
    try:
        from mlxtend.frequent_patterns import fpgrowth
        from mlxtend.preprocessing import TransactionEncoder
        import pandas as pd
    except ImportError:
        print("Error: mlxtend library is required for FP-Growth analysis.")
        print("Install it with: pip install mlxtend")
        sys.exit(1)
    
    if not tag_sets:
        return []
    
    # Convert tag sets to list of lists for TransactionEncoder
    transactions = [list(ts) for ts in tag_sets]
    
    # Encode transactions
    te = TransactionEncoder()
    te_array = te.fit_transform(transactions)
    df = pd.DataFrame(te_array, columns=te.columns_)
    
    # Run FP-Growth
    try:
        frequent_itemsets = fpgrowth(df, min_support=min_support, use_colnames=True)
    except Exception as e:
        print(f"Error running FP-Growth: {e}")
        return []
    
    if frequent_itemsets.empty:
        return []
    
    # Filter by item count
    frequent_itemsets['length'] = frequent_itemsets['itemsets'].apply(len)
    
    if min_items > 1:
        frequent_itemsets = frequent_itemsets[frequent_itemsets['length'] >= min_items]
    
    if max_items is not None:
        frequent_itemsets = frequent_itemsets[frequent_itemsets['length'] <= max_items]
    
    # Sort by support descending
    frequent_itemsets = frequent_itemsets.sort_values('support', ascending=False)
    
    # Convert to list of tuples
    result = [
        (row['itemsets'], row['support'])
        for _, row in frequent_itemsets.iterrows()
    ]
    
    return result


def format_itemset(itemset: frozenset, support: float, total_files: int) -> str:
    """Format an itemset for display."""
    count = int(support * total_files)
    tags = sorted(itemset)
    return f"[{support*100:5.1f}%] ({count:4d}) {', '.join(tags)}"


def analyze_tags(
    directory: str,
    recursive: bool = True,
    min_support: float = 0.05,
    min_items: int = 1,
    max_items: int = None,
    top_n: int = 100,
    exclude_patterns: List[str] = None
) -> AnalysisResult:
    """
    Perform complete tag analysis on a directory.
    
    Args:
        directory: Directory to analyze
        recursive: Whether to scan subdirectories
        min_support: Minimum support threshold
        min_items: Minimum items per itemset
        max_items: Maximum items per itemset
        top_n: Number of top itemsets to return
        exclude_patterns: Tag prefixes to exclude
        
    Returns:
        AnalysisResult with all analysis data
    """
    result = AnalysisResult()
    
    # Collect tag sets
    print(f"Scanning directory: {directory}")
    tag_sets, tag_counter = collect_tag_sets(directory, recursive, exclude_patterns)
    
    result.total_files = len(tag_sets)
    result.tag_sets = tag_sets
    result.tag_frequency = dict(tag_counter)
    result.unique_tags = len(tag_counter)
    result.total_tags = sum(tag_counter.values())
    
    if not tag_sets:
        print("No tag data found.")
        return result
    
    print(f"Found {result.total_files} files with tags")
    print(f"Total tags: {result.total_tags}, Unique tags: {result.unique_tags}")
    print()
    
    # Run FP-Growth
    print(f"Running FP-Growth (min_support={min_support}, min_items={min_items}, max_items={max_items})...")
    frequent_itemsets = fp_growth(tag_sets, min_support, min_items, max_items)
    
    # Limit to top_n
    result.frequent_itemsets = frequent_itemsets[:top_n] if top_n else frequent_itemsets
    
    return result


def print_results(result: AnalysisResult, show_single: bool = False):
    """Print analysis results to console."""
    if not result.frequent_itemsets:
        print("No frequent itemsets found. Try lowering --min-support.")
        return
    
    print(f"\nFound {len(result.frequent_itemsets)} frequent itemsets:")
    print("-" * 70)
    
    for itemset, support in result.frequent_itemsets:
        if len(itemset) == 1 and not show_single:
            continue
        print(format_itemset(itemset, support, result.total_files))


def export_results(result: AnalysisResult, output_path: str):
    """Export analysis results to JSON file."""
    export_data = {
        "summary": {
            "total_files": result.total_files,
            "total_tags": result.total_tags,
            "unique_tags": result.unique_tags,
        },
        "tag_frequency": dict(sorted(
            result.tag_frequency.items(), 
            key=lambda x: x[1], 
            reverse=True
        )),
        "frequent_itemsets": [
            {
                "tags": sorted(list(itemset)),
                "support": support,
                "count": int(support * result.total_files)
            }
            for itemset, support in result.frequent_itemsets
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze tag patterns from Hydrus sidecar JSON files using FP-Growth.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s ./download                      # Basic analysis
    %(prog)s ./download --min-support 0.1    # Higher support threshold (more common patterns)
    %(prog)s ./download --min-support 0.01   # Lower threshold (rarer patterns)
    %(prog)s ./download --min-items 2        # Only show tag combinations (2+ tags)
    %(prog)s ./download --max-items 3        # Limit itemset size
    %(prog)s ./download --top 100            # Show top 100 patterns
    %(prog)s ./download --exclude-rating     # Exclude rating:* tags
    %(prog)s ./download -o analysis.json     # Export results to JSON

Support Value:
    Support represents how often a tag combination appears.
    A support of 0.1 means the combination appears in 10% of images.
        """
    )
    
    parser.add_argument(
        'directory',
        help='Directory containing sidecar JSON files'
    )
    
    parser.add_argument(
        '-s', '--min-support',
        type=float,
        default=0.05,
        help='Minimum support threshold (default: 0.05 = 5%%)'
    )
    
    parser.add_argument(
        '--min-items',
        type=int,
        default=1,
        help='Minimum number of items in an itemset (default: 1)'
    )
    
    parser.add_argument(
        '--max-items',
        type=int,
        default=None,
        help='Maximum number of items in an itemset (default: no limit)'
    )
    
    parser.add_argument(
        '-n', '--top',
        type=int,
        default=100,
        help='Number of top frequent itemsets to show (default: 100)'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Only scan the specified directory, not subdirectories'
    )
    
    parser.add_argument(
        '--exclude-rating',
        action='store_true',
        help='Exclude rating:* tags from analysis'
    )
    
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        help='Exclude tags starting with this prefix (can be used multiple times)'
    )
    
    parser.add_argument(
        '--show-single',
        action='store_true',
        help='Show single-tag itemsets in output'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Export results to JSON file'
    )
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory")
        sys.exit(1)
    
    # Build exclude patterns
    exclude_patterns = args.exclude.copy()
    if args.exclude_rating:
        exclude_patterns.append('rating:')
    
    # Run analysis
    result = analyze_tags(
        directory=args.directory,
        recursive=not args.no_recursive,
        min_support=args.min_support,
        min_items=args.min_items,
        max_items=args.max_items,
        top_n=args.top,
        exclude_patterns=exclude_patterns if exclude_patterns else None
    )
    
    # Print results
    print_results(result, show_single=args.show_single)
    
    # Export if requested
    if args.output:
        export_results(result, args.output)


if __name__ == '__main__':
    main()
