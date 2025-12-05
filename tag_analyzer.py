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
    python tag_analyzer.py ./download --exclude-common 20  # Exclude top 20 most common tags
    python tag_analyzer.py ./download --min-lift 1.5     # Only show itemsets with lift > 1.5
    python tag_analyzer.py ./download -o result.json     # Export results to JSON

Output:
    Displays frequent tag combinations sorted by support (frequency) or lift (interestingness).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ItemsetInfo:
    """Information about a frequent itemset."""
    itemset: frozenset
    support: float
    lift: float = 1.0  # Lift = 1 means independent, > 1 means positive correlation


@dataclass
class AnalysisResult:
    """Result of tag analysis."""
    total_files: int = 0
    total_tags: int = 0
    unique_tags: int = 0
    tag_sets: List[Set[str]] = field(default_factory=list)
    tag_frequency: Dict[str, int] = field(default_factory=dict)
    frequent_itemsets: List[ItemsetInfo] = field(default_factory=list)
    excluded_common_tags: List[str] = field(default_factory=list)


def collect_tag_sets(
    directory: str,
    recursive: bool = True,
    exclude_patterns: List[str] = None,
    exclude_tags: Set[str] = None
) -> Tuple[List[Set[str]], Counter]:
    """
    Collect all tag sets from sidecar JSON files in a directory.
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        exclude_patterns: Tag prefixes to exclude (e.g., ['rating:'])
        exclude_tags: Specific tags to exclude
        
    Returns:
        Tuple of (list of tag sets, tag frequency counter)
    """
    tag_sets = []
    tag_counter = Counter()
    exclude_patterns = exclude_patterns or []
    exclude_tags = exclude_tags or set()
    
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
            
            # Filter out excluded patterns and specific tags
            filtered_tags = set()
            for tag in tags:
                if tag in exclude_tags:
                    continue
                if any(tag.startswith(pattern) for pattern in exclude_patterns):
                    continue
                filtered_tags.add(tag)
            
            if filtered_tags:
                tag_sets.append(filtered_tags)
                tag_counter.update(filtered_tags)
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_path}: {e}")
            continue
    
    return tag_sets, tag_counter


def get_common_tags(directory: str, recursive: bool = True, top_n: int = 20) -> List[str]:
    """
    Get the most common tags from a directory (before any filtering).
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        top_n: Number of top tags to return
        
    Returns:
        List of most common tag names
    """
    _, tag_counter = collect_tag_sets(directory, recursive, exclude_patterns=None, exclude_tags=None)
    return [tag for tag, _ in tag_counter.most_common(top_n)]


def calculate_lift(
    itemset: frozenset,
    itemset_support: float,
    tag_supports: Dict[str, float]
) -> float:
    """
    Calculate lift for an itemset.
    
    Lift = P(A ∩ B) / (P(A) * P(B))
    Lift > 1 means positive correlation (tags appear together more than expected)
    Lift = 1 means independent
    Lift < 1 means negative correlation (tags appear together less than expected)
    
    Args:
        itemset: The itemset (frozenset of tags)
        itemset_support: Support of the itemset
        tag_supports: Dictionary mapping each tag to its individual support
        
    Returns:
        Lift value
    """
    if len(itemset) < 2:
        return 1.0
    
    # Calculate expected support if tags were independent
    expected_support = 1.0
    for tag in itemset:
        if tag in tag_supports:
            expected_support *= tag_supports[tag]
        else:
            return 1.0  # Can't calculate if tag support unknown
    
    if expected_support == 0:
        return 1.0
    
    return itemset_support / expected_support


def fp_growth_with_lift(
    tag_sets: List[Set[str]],
    min_support: float = 0.05,
    min_items: int = 1,
    max_items: int = None,
    min_lift: float = None
) -> Tuple[List[ItemsetInfo], Dict[str, float]]:
    """
    Find frequent itemsets using FP-Growth algorithm and calculate lift.
    
    Args:
        tag_sets: List of tag sets
        min_support: Minimum support threshold (0.0 to 1.0)
        min_items: Minimum number of items in an itemset
        max_items: Maximum number of items in an itemset (None for no limit)
        min_lift: Minimum lift threshold (None for no filtering)
        
    Returns:
        Tuple of (list of ItemsetInfo, dict of tag supports)
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
        return [], {}
    
    # Convert tag sets to list of lists for TransactionEncoder
    transactions = [list(ts) for ts in tag_sets]
    
    # Encode transactions
    te = TransactionEncoder()
    te_array = te.fit_transform(transactions)
    df = pd.DataFrame(te_array, columns=te.columns_)
    
    # Calculate individual tag supports
    tag_supports = {col: df[col].mean() for col in df.columns}
    
    # Run FP-Growth
    try:
        frequent_itemsets = fpgrowth(df, min_support=min_support, use_colnames=True)
    except Exception as e:
        print(f"Error running FP-Growth: {e}")
        return [], tag_supports
    
    if frequent_itemsets.empty:
        return [], tag_supports
    
    # Filter by item count
    frequent_itemsets['length'] = frequent_itemsets['itemsets'].apply(len)
    
    if min_items > 1:
        frequent_itemsets = frequent_itemsets[frequent_itemsets['length'] >= min_items]
    
    if max_items is not None:
        frequent_itemsets = frequent_itemsets[frequent_itemsets['length'] <= max_items]
    
    # Calculate lift and create ItemsetInfo objects
    results = []
    for _, row in frequent_itemsets.iterrows():
        itemset = row['itemsets']
        support = row['support']
        lift = calculate_lift(itemset, support, tag_supports)
        
        # Filter by lift if specified
        if min_lift is not None and lift < min_lift:
            continue
        
        results.append(ItemsetInfo(
            itemset=itemset,
            support=support,
            lift=lift
        ))
    
    return results, tag_supports


def format_itemset(info: ItemsetInfo, total_files: int, show_lift: bool = True) -> str:
    """Format an itemset for display."""
    count = int(info.support * total_files)
    tags = sorted(info.itemset)
    
    if show_lift and len(info.itemset) >= 2:
        return f"[{info.support*100:5.1f}%] ({count:4d}) [lift:{info.lift:5.2f}] {', '.join(tags)}"
    else:
        return f"[{info.support*100:5.1f}%] ({count:4d}) {', '.join(tags)}"


def analyze_tags(
    directory: str,
    recursive: bool = True,
    min_support: float = 0.05,
    min_items: int = 1,
    max_items: int = None,
    top_n: int = 100,
    exclude_patterns: List[str] = None,
    exclude_common: int = None,
    min_lift: float = None,
    sort_by_lift: bool = False
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
        exclude_common: Number of most common tags to exclude
        min_lift: Minimum lift threshold
        sort_by_lift: Sort by lift instead of support
        
    Returns:
        AnalysisResult with all analysis data
    """
    result = AnalysisResult()
    
    # First pass: get common tags if needed
    exclude_tags = set()
    if exclude_common and exclude_common > 0:
        print(f"Finding top {exclude_common} common tags to exclude...")
        common_tags = get_common_tags(directory, recursive, exclude_common)
        exclude_tags = set(common_tags)
        result.excluded_common_tags = common_tags
        print(f"Excluding: {', '.join(common_tags)}")
        print()
    
    # Collect tag sets
    print(f"Scanning directory: {directory}")
    tag_sets, tag_counter = collect_tag_sets(
        directory, recursive, exclude_patterns, exclude_tags
    )
    
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
    
    # Run FP-Growth with lift calculation
    lift_info = f", min_lift={min_lift}" if min_lift else ""
    print(f"Running FP-Growth (min_support={min_support}, min_items={min_items}, max_items={max_items}{lift_info})...")
    
    frequent_itemsets, _ = fp_growth_with_lift(
        tag_sets, min_support, min_items, max_items, min_lift
    )
    
    # Sort results
    if sort_by_lift:
        frequent_itemsets.sort(key=lambda x: (-x.lift, -x.support))
    else:
        frequent_itemsets.sort(key=lambda x: (-x.support, -x.lift))
    
    # Limit to top_n
    result.frequent_itemsets = frequent_itemsets[:top_n] if top_n else frequent_itemsets
    
    return result


def print_results(result: AnalysisResult, show_single: bool = False, show_lift: bool = True):
    """Print analysis results to console."""
    if not result.frequent_itemsets:
        print("No frequent itemsets found. Try lowering --min-support or --min-lift.")
        return
    
    print(f"\nFound {len(result.frequent_itemsets)} frequent itemsets:")
    print("-" * 80)
    
    for info in result.frequent_itemsets:
        if len(info.itemset) == 1 and not show_single:
            continue
        print(format_itemset(info, result.total_files, show_lift))


def export_results(result: AnalysisResult, output_path: str):
    """Export analysis results to JSON file."""
    export_data = {
        "summary": {
            "total_files": result.total_files,
            "total_tags": result.total_tags,
            "unique_tags": result.unique_tags,
        },
        "excluded_common_tags": result.excluded_common_tags,
        "tag_frequency": dict(sorted(
            result.tag_frequency.items(), 
            key=lambda x: x[1], 
            reverse=True
        )),
        "frequent_itemsets": [
            {
                "tags": sorted(list(info.itemset)),
                "support": info.support,
                "count": int(info.support * result.total_files),
                "lift": info.lift
            }
            for info in result.frequent_itemsets
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
    %(prog)s ./download --exclude-common 20  # Exclude top 20 most common tags
    %(prog)s ./download --min-lift 1.5       # Only show correlated tags (lift > 1.5)
    %(prog)s ./download --sort-by-lift       # Sort by lift (interestingness) instead of support
    %(prog)s ./download -o analysis.json     # Export results to JSON

Support Value:
    Support represents how often a tag combination appears.
    A support of 0.1 means the combination appears in 10%% of images.

Lift Value:
    Lift measures how much more often tags appear together than expected by chance.
    Lift > 1: Tags are positively correlated (appear together more than expected)
    Lift = 1: Tags are independent (no special relationship)
    Lift < 1: Tags are negatively correlated (appear together less than expected)
    
    Example: If "blonde_hair" appears in 20%% and "blue_eyes" in 10%% of images,
    random chance would give 2%% co-occurrence. If actual is 5%%, lift = 5/2 = 2.5
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
        '--exclude-common',
        type=int,
        default=None,
        metavar='N',
        help='Exclude the top N most common tags from analysis'
    )
    
    parser.add_argument(
        '--min-lift',
        type=float,
        default=None,
        help='Minimum lift threshold (only show positively correlated tags)'
    )
    
    parser.add_argument(
        '--sort-by-lift',
        action='store_true',
        help='Sort results by lift (interestingness) instead of support (frequency)'
    )
    
    parser.add_argument(
        '--show-single',
        action='store_true',
        help='Show single-tag itemsets in output'
    )
    
    parser.add_argument(
        '--no-lift',
        action='store_true',
        help='Do not show lift values in output'
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
        exclude_patterns=exclude_patterns if exclude_patterns else None,
        exclude_common=args.exclude_common,
        min_lift=args.min_lift,
        sort_by_lift=args.sort_by_lift
    )
    
    # Print results
    print_results(result, show_single=args.show_single, show_lift=not args.no_lift)
    
    # Export if requested
    if args.output:
        export_results(result, args.output)


if __name__ == '__main__':
    main()
