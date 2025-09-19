# name: __init__.py
# path: skills/living_truth_partner/__init__.py
# role: Expose Living Truth Partner CLI entry
# deps: skills.living_truth_partner.cli
# inputs: args
# outputs: api function

from __future__ import annotations

from skills.living_truth_partner.cli import api

__all__ = ["api"]
