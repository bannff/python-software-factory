#!/usr/bin/env python3
"""
Sync label definitions from labels.yml to GitHub.

This script reads the canonical label definitions from labels.yml
and creates or updates them in the GitHub repository. It's idempotent
and safe to run multiple times.

Usage:
    python scripts/sync_labels.py [--dry-run]

Environment variables:
    GITHUB_TOKEN: Required for authentication (or use gh CLI auth)
    GITHUB_REPOSITORY: Optional, defaults to bannff/python-factory
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def load_labels(labels_file: Path) -> list[dict[str, str]]:
    """Load label definitions from YAML file."""
    if not labels_file.exists():
        print(f"Error: Labels file not found: {labels_file}")
        sys.exit(1)
    
    try:
        with open(labels_file) as f:
            labels = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse {labels_file}: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"Error: Failed to read {labels_file}: {e}")
        sys.exit(1)
    
    if not isinstance(labels, list):
        print("Error: labels.yml must contain a list of label definitions")
        sys.exit(1)
    
    # Validate label structure
    for label in labels:
        if "name" not in label:
            print(f"Error: Label missing 'name' field: {label}")
            sys.exit(1)
        if "color" not in label:
            print(f"Error: Label missing 'color' field: {label['name']}")
            sys.exit(1)
    
    return labels


def get_existing_labels(repo: str) -> dict[str, dict[str, Any]]:
    """Get existing labels from GitHub using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "label", "list", "--repo", repo, "--json", "name,color,description", "--limit", "1000"],
            capture_output=True,
            text=True,
            check=True,
        )
        labels = json.loads(result.stdout)
        return {label["name"]: label for label in labels}
    except subprocess.CalledProcessError as e:
        print(f"Error fetching existing labels: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: gh CLI not found. Install from https://cli.github.com/")
        sys.exit(1)


def create_label(repo: str, label: dict[str, str], dry_run: bool = False) -> None:
    """Create a new label in GitHub."""
    name = label["name"]
    color = label["color"]
    description = label.get("description", "")
    
    cmd = [
        "gh", "label", "create", name,
        "--repo", repo,
        "--color", color,
    ]
    if description:
        cmd.extend(["--description", description])
    
    if dry_run:
        print(f"[DRY RUN] Would create: {name}")
        return
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Created: {name}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create {name}: {e.stderr}")


def update_label(repo: str, label: dict[str, str], dry_run: bool = False) -> None:
    """Update an existing label in GitHub."""
    name = label["name"]
    color = label["color"]
    description = label.get("description", "")
    
    cmd = [
        "gh", "label", "edit", name,
        "--repo", repo,
        "--color", color,
    ]
    if description:
        cmd.extend(["--description", description])
    
    if dry_run:
        print(f"[DRY RUN] Would update: {name}")
        return
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Updated: {name}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to update {name}: {e.stderr}")


def sync_labels(
    labels_file: Path,
    repo: str,
    dry_run: bool = False,
) -> None:
    """Sync labels from file to GitHub."""
    labels = load_labels(labels_file)
    existing = get_existing_labels(repo)
    
    print(f"Syncing {len(labels)} labels to {repo}")
    if dry_run:
        print("DRY RUN MODE - No changes will be made\n")
    
    created = 0
    updated = 0
    unchanged = 0
    
    for label in labels:
        name = label["name"]
        
        if name not in existing:
            create_label(repo, label, dry_run)
            created += 1
        else:
            # Check if update is needed
            existing_label = existing[name]
            needs_update = False
            
            # Normalize colors for comparison (remove leading zeros)
            existing_color = existing_label["color"].lstrip("0") or "0"
            new_color = label["color"].lstrip("0") or "0"
            if existing_color != new_color:
                needs_update = True
            
            existing_desc = existing_label.get("description") or ""
            new_desc = label.get("description", "")
            if existing_desc != new_desc:
                needs_update = True
            
            if needs_update:
                update_label(repo, label, dry_run)
                updated += 1
            else:
                unchanged += 1
                if not dry_run:
                    print(f"  Unchanged: {name}")
    
    print(f"\nSummary:")
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Unchanged: {unchanged}")
    print(f"  Total: {len(labels)}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync label definitions to GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync labels to the default repository
  python scripts/sync_labels.py
  
  # Preview changes without applying them
  python scripts/sync_labels.py --dry-run
  
  # Sync to a different repository
  GITHUB_REPOSITORY=owner/repo python scripts/sync_labels.py
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--labels-file",
        type=Path,
        default=Path("labels.yml"),
        help="Path to labels.yml (default: labels.yml)",
    )
    
    args = parser.parse_args()
    
    # Get repository from environment or use default
    repo = os.environ.get("GITHUB_REPOSITORY", "bannff/python-factory")
    
    sync_labels(args.labels_file, repo, args.dry_run)


if __name__ == "__main__":
    main()
