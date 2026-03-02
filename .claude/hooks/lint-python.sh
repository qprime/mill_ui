#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUFF="$PROJECT_DIR/.venv/bin/ruff"

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

if [[ -z "$file_path" || "$file_path" != *.py ]]; then
    exit 0
fi

if [[ ! -f "$file_path" ]]; then
    exit 0
fi

if [[ ! -x "$RUFF" ]]; then
    echo "ruff not found at $RUFF" >&2
    exit 0
fi

errors=""

lint_output=$("$RUFF" check "$file_path" 2>&1) || errors+="$lint_output"$'\n'
format_output=$("$RUFF" format --check "$file_path" 2>&1) || errors+="$format_output"$'\n'

if [[ -n "$errors" ]]; then
    echo "$errors" >&2
    exit 2
fi
