"""Configuration for MCP server."""

from pathlib import Path
import os

# Output directory for generated files
# Can be overridden via MILL_UI_OUTPUT_DIR environment variable
DEFAULT_OUTPUT_DIR = Path("/home/squinlan/cliff_ai/memories/cam_projects/mill_ui")

def get_output_dir() -> Path:
    """Get the output directory for generated files."""
    env_path = os.environ.get("MILL_UI_OUTPUT_DIR")
    if env_path:
        return Path(env_path)
    return DEFAULT_OUTPUT_DIR

def ensure_output_dir() -> Path:
    """Ensure output directory exists and return it."""
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
