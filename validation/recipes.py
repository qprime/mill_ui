from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

RECIPES_ROOT = Path(__file__).resolve().parent.parent / "docs" / "recipes"
PML_SUFFIX = ".pml.yml"
NEST_SUFFIX = ".nest.yml"
OUTPUT_DIR_NAME = "output"


@dataclass(frozen=True)
class Recipe:
    name: str
    category: str
    path: Path
    pml_sources: tuple[Path, ...]
    nest_sources: tuple[Path, ...]


def _is_input(path: Path) -> bool:
    return path.is_file() and path.name.endswith((PML_SUFFIX, NEST_SUFFIX))


def _inputs(folder: Path, suffix: str) -> tuple[Path, ...]:
    return tuple(sorted(path for path in folder.glob(f"*{suffix}") if path.is_file()))


def _subfolders(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if path.is_dir()) if folder.is_dir() else []


def recipe_at(path: Path) -> Recipe | None:
    pml_sources = _inputs(path, PML_SUFFIX)
    nest_sources = _inputs(path, NEST_SUFFIX)
    if not pml_sources and not nest_sources:
        return None
    return Recipe(
        name=path.name,
        category=path.parent.name,
        path=path,
        pml_sources=pml_sources,
        nest_sources=nest_sources,
    )


def find_recipes(root: Path = RECIPES_ROOT) -> tuple[Recipe, ...]:
    recipes: dict[str, Recipe] = {}
    for category in _subfolders(root):
        for folder in _subfolders(category):
            recipe = recipe_at(folder)
            if recipe is None:
                continue
            if recipe.name in recipes:
                raise ValueError(f"Two recipes are named {recipe.name}: {recipes[recipe.name].path} and {recipe.path}")
            recipes[recipe.name] = recipe
    return tuple(recipes.values())


def find_recipe(name: str, root: Path = RECIPES_ROOT) -> Recipe:
    for recipe in find_recipes(root):
        if recipe.name == name:
            return recipe
    raise KeyError(f"No recipe named {name} under {root}")


def misplaced_inputs(root: Path = RECIPES_ROOT) -> tuple[Path, ...]:
    misplaced = []
    for path in sorted(root.rglob("*")):
        if not _is_input(path):
            continue
        parts = path.relative_to(root).parts
        in_recipe_folder = len(parts) == 3
        in_recipe_output = len(parts) > 3 and parts[2] == OUTPUT_DIR_NAME
        if not in_recipe_folder and not in_recipe_output:
            misplaced.append(path)
    return tuple(misplaced)


def recipe_job_stem(recipe: Recipe, source: Path) -> str:
    return recipe.name if len(recipe.pml_sources) == 1 else source.stem
