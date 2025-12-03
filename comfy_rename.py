#!/usr/bin/env python
"""
Batch ComfyUI image detection and renaming tool.
Recursively scans a directory for PNG files and renames ComfyUI generated images.

Usage:
    python comfy_rename.py <directory> [options]
    
Options:
    -r, --recursive     Scan subdirectories (default: True)
    -n, --dry-run       Only show what would be renamed without actually renaming
    -h, --help          Show this help message

Examples:
    python comfy_rename.py ./download
    python comfy_rename.py ./download --dry-run
    python comfy_rename.py ./download --no-recursive
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from post_process import process_directory


def main():
    parser = argparse.ArgumentParser(
        description='Detect and rename ComfyUI generated PNG images.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s ./download                 # Scan download folder recursively
    %(prog)s ./download --dry-run       # Preview changes without renaming
    %(prog)s ./download --no-recursive  # Only scan top-level directory
    %(prog)s .                          # Scan current directory
        """
    )
    
    parser.add_argument(
        'directory',
        help='Directory to scan for PNG files'
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
        help='Only show what would be renamed without actually renaming'
    )
    
    args = parser.parse_args()
    
    # Validate directory
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)
    
    # Convert to absolute path for cleaner output
    directory = os.path.abspath(args.directory)
    
    print(f"Scanning: {directory}")
    print(f"Recursive: {args.recursive}")
    print(f"Dry run: {args.dry_run}")
    print("-" * 50)
    
    # Process directory
    stats = process_directory(
        directory,
        recursive=args.recursive,
        dry_run=args.dry_run
    )
    
    # Print summary
    print("-" * 50)
    print("Summary:")
    print(f"  Total PNG files scanned: {stats['total']}")
    print(f"  Successfully processed:  {stats['processed']}")
    print(f"  ComfyUI images {'found' if args.dry_run else 'renamed'}:    {stats['renamed']}")
    if stats['errors'] > 0:
        print(f"  Errors:                  {stats['errors']}")
    
    if args.dry_run and stats['renamed'] > 0:
        print(f"\nRun without --dry-run to actually rename {stats['renamed']} file(s).")


if __name__ == '__main__':
    main()
