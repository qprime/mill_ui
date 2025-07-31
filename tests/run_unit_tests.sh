#!/bin/bash
# Activate tests/venv, set PYTHONPATH, cd to repo root, run pytest as a module

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SCRIPT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Python venv not found in $VENV_DIR. Creating..."
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install -q --upgrade pip pytest

export PYTHONPATH="$REPO_ROOT"
cd "$REPO_ROOT" || exit 1

python3 -m pytest tests/unit -v
