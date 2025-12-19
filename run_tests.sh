#!/bin/bash
# Test runner script for mill_ui
# Uses PYTHONPATH to run tests from flat package layout

set -e

# Use Python from venv if available, otherwise system python3
if [ -f "./venv/bin/python3" ]; then
    PYTHON="./venv/bin/python3"
else
    PYTHON="python3"
fi

# Set PYTHONPATH to current directory
export PYTHONPATH=.

# Default: run all tests
if [ $# -eq 0 ]; then
    echo "=== Running all test suites ==="
    echo

    echo "--- PML Parser Tests ---"
    $PYTHON -m tests.run_pml_tests
    echo

    echo "--- Edge Intent Tests ---"
    $PYTHON -m tests.run_edge_tests
    echo

    echo "--- Resolution Tests ---"
    $PYTHON -m tests.run_resolution_tests
    echo

    echo "--- Removal Intent Tests ---"
    $PYTHON -m tests.run_removal_intent_tests
    echo

    echo "=== All core tests passed ==="
else
    # Run specific test
    TEST_NAME=$1
    echo "Running test: $TEST_NAME"
    $PYTHON -m tests.$TEST_NAME
fi
