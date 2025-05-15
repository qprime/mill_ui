#!/bin/bash
# CLIFF AI post-commit hook

echo "[CLIFF] Updating script registry..."
python3 scripts/metadata/update_script_registry.py

echo "[CLIFF] Regenerating project graph..."
python3 scripts/metadata/generate_project_graph.py

echo "[CLIFF] Regenerating memory graph..."
python3 scripts/metadata/generate_memory_graph.py

echo "[CLIFF] Refreshing Chroma project summaries..."
python3 scripts/embedding/rag_loader.py

echo "[CLIFF] Post-commit tasks complete."

