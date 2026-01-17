# cli/generate_golden.py - Generate golden baseline metrics for recipes
#
# Creates and updates golden baseline files in tests/golden/ for regression testing.
# See docs/cam_validation_plan.md Section 6.1 for structure.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validation.runner import validate_recipe, ValidationOptions
from validation.regression import GoldenStore, create_golden_from_recipe


def main() -> int:
    """Main entry point for golden generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate golden baseline metrics for recipes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Generate golden for a single recipe
  python -m cli.generate_golden --recipe docs/recipes/01_simple_profile

  # Generate golden for all recipes in a directory
  python -m cli.generate_golden --all-recipes docs/recipes

  # List existing golden baselines
  python -m cli.generate_golden --list

  # Update a specific golden baseline
  python -m cli.generate_golden --recipe docs/recipes/01_simple_profile --update

  # Specify custom golden store location
  python -m cli.generate_golden --recipe docs/recipes/01_simple_profile --store tests/golden
        """,
    )

    # Actions
    action_group = parser.add_argument_group("Actions")
    action_group.add_argument(
        "--recipe", "-r",
        metavar="DIR",
        help="Generate golden for a single recipe directory",
    )
    action_group.add_argument(
        "--all-recipes",
        metavar="DIR",
        help="Generate golden for all recipes in a directory",
    )
    action_group.add_argument(
        "--list", "-l",
        action="store_true",
        help="List existing golden baselines",
    )

    # Options
    options_group = parser.add_argument_group("Options")
    options_group.add_argument(
        "--store", "-s",
        metavar="DIR",
        default="tests/golden",
        help="Golden store directory (default: tests/golden)",
    )
    options_group.add_argument(
        "--update", "-u",
        action="store_true",
        help="Update existing golden (otherwise skip if exists)",
    )
    options_group.add_argument(
        "--force", "-f",
        action="store_true",
        help="Generate even if invariant checks fail (skips broken recipes on errors)",
    )
    options_group.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without actually doing it",
    )
    options_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress status messages",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.recipe and not args.all_recipes and not args.list:
        parser.error("One of --recipe, --all-recipes, or --list is required")

    try:
        store = GoldenStore(args.store)

        if args.list:
            return list_golden(store, args)
        elif args.all_recipes:
            return generate_all(store, args)
        else:
            return generate_single(store, args)

    except Exception as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1


def list_golden(store: GoldenStore, args: argparse.Namespace) -> int:
    """List existing golden baselines."""
    if not store.exists():
        print(f"Golden store not found at: {store.base_path}")
        return 0

    entries = store.list_entries()
    if not entries:
        print("No golden baselines found")
        return 0

    print(f"Golden baselines in {store.base_path}:")
    print()

    index = store.load_index()
    for name in sorted(entries):
        entry = index.entries[name]
        metrics_path = store.get_metrics_path(name)
        exists = "✓" if metrics_path.exists() else "✗"
        print(f"  {exists} {name}")
        print(f"      Source: {entry.source_file}")
        print(f"      Updated: {entry.updated_at[:10]}")

    print()
    print(f"Total: {len(entries)} baselines")
    return 0


def generate_all(store: GoldenStore, args: argparse.Namespace) -> int:
    """Generate golden for all recipes in a directory."""
    recipes_dir = Path(args.all_recipes)

    if not recipes_dir.exists():
        print(f"Error: Recipes directory not found: {args.all_recipes}", file=sys.stderr)
        return 1

    # Find all recipe directories
    recipe_dirs = []
    for item in sorted(recipes_dir.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            # Check if it has output/
            if (item / "output").exists():
                recipe_dirs.append(item)

    if not recipe_dirs:
        print(f"No recipe directories found in: {args.all_recipes}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Found {len(recipe_dirs)} recipes")

    # Initialize store
    if not args.dry_run:
        store.initialize()

    success = 0
    skipped = 0
    failed = 0

    for recipe_dir in recipe_dirs:
        name = recipe_dir.name

        # Check if already exists (both index entry AND actual metrics file)
        if store.has_entry(name) and store.get_metrics_path(name).exists() and not args.update:
            if not args.quiet:
                print(f"  SKIP {name} (exists, use --update to overwrite)")
            skipped += 1
            continue

        # Generate
        result = generate_recipe(store, recipe_dir, name, args)
        if result == 0:
            success += 1
        else:
            failed += 1

    if not args.quiet:
        print()
        print(f"Results: {success} generated, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


def generate_single(store: GoldenStore, args: argparse.Namespace) -> int:
    """Generate golden for a single recipe."""
    recipe_dir = Path(args.recipe)

    if not recipe_dir.exists():
        print(f"Error: Recipe directory not found: {args.recipe}", file=sys.stderr)
        return 1

    if not recipe_dir.is_dir():
        print(f"Error: Not a directory: {args.recipe}", file=sys.stderr)
        return 1

    name = recipe_dir.name

    # Check if already exists (both index entry AND actual metrics file)
    if store.has_entry(name) and store.get_metrics_path(name).exists() and not args.update:
        if not args.quiet:
            print(f"Golden baseline already exists for: {name}")
            print("Use --update to overwrite")
        return 0

    # Initialize store
    if not args.dry_run:
        store.initialize()

    return generate_recipe(store, recipe_dir, name, args)


def generate_recipe(
    store: GoldenStore,
    recipe_dir: Path,
    name: str,
    args: argparse.Namespace,
) -> int:
    """Generate golden for a single recipe."""
    if not args.quiet:
        action = "UPDATE" if store.has_entry(name) else "CREATE"
        if args.dry_run:
            print(f"  DRY-RUN {action} {name}")
            return 0
        print(f"  {action} {name}...", end=" ", flush=True)

    # Run validation to extract metrics
    options = ValidationOptions(
        extract_metrics=True,
        check_invariants=True,
        check_assertions=False,  # Don't need assertions for golden
        check_regressions=False,  # No golden to compare against yet
    )

    try:
        result = validate_recipe(str(recipe_dir), options=options)
    except Exception as e:
        if not args.quiet:
            print(f"FAIL (validation error: {e})")
        return 1

    # Check for validation failures
    if result.invariants.failed > 0 and not args.force:
        if not args.quiet:
            print(f"FAIL ({result.invariants.failed} invariant failures)")
            print(f"      Use --force to generate anyway")
        return 1

    # Find source PML
    source_pml = None
    for candidate in ["example.pml", "source.pml"]:
        pml_path = recipe_dir / candidate
        if pml_path.exists():
            source_pml = pml_path
            break

    # Save golden
    create_golden_from_recipe(
        store=store,
        recipe_name=name,
        metrics=result.metrics,
        source_pml_path=source_pml,
    )

    if not args.quiet:
        metric_types = list(result.metrics.keys())
        print(f"OK ({', '.join(metric_types)})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
