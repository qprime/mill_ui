
from __future__ import annotations

from pathlib import Path


def svg_to_pdf(svg_string: str, output_path: str | Path) -> None:
    try:
        import cairosvg
    except ImportError as e:
        raise ImportError(
            "cairosvg is required for PDF export. Install with: pip install cairosvg"
        ) from e

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cairosvg.svg2pdf(bytestring=svg_string.encode("utf-8"), write_to=str(output_path))


__all__ = ["svg_to_pdf"]
