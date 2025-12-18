"""Canonicalization rules for LayoutAST.

Ensures semantic equivalence through normalization:
- Stable key ordering (via JSON sort_keys)
- Numeric normalization (preserve precision, no spurious decimals)
- Default value injection where appropriate
"""

from __future__ import annotations

from skills.mill_ui.layout_ast.layout import LayoutAST


def canonicalize_layout(ast: LayoutAST) -> LayoutAST:
    """Apply canonicalization rules to LayoutAST.

    Currently a pass-through since:
    - Key ordering handled by json.dumps(sort_keys=True)
    - Numeric values preserved as-is from input
    - No default injection needed for Stage 3

    Future stages may add:
    - Default value injection for optional fields
    - Numeric normalization (e.g., 1.0 → 1.0, not 1)
    - Collection sorting where order-insensitive

    Args:
        ast: Input LayoutAST

    Returns:
        Canonicalized LayoutAST (currently identical to input)
    """
    # For Stage 3, canonicalization is minimal
    # Key ordering is handled by JSON emission
    # Future normalization rules will be added here as needed
    return ast
