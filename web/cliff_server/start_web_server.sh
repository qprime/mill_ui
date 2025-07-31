#!/bin/bash
set -e
set -o pipefail

# Set project root as working directory
cd /home/squinlan/cliff_ai

# (Optional) Set PYTHONPATH for absolute safety
export PYTHONPATH=/home/squinlan/cliff_ai

# (Optional) Activate virtualenv if you use one
# source /home/squinlan/cliff_ai/.venv/bin/activate

# (Optional) Log start time and environment for debugging
echo "=== Starting Cliff Web Server ==="
echo "Date: $(date)"
echo "CWD:  $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo "User: $(whoami)"
echo "---------------------------------"

# Run the web server (adjust the module as needed!)
# Prefer `python3 -m web.cliff_server.app` over direct script call
python3 -m web.cliff_server.app "$@" 2>&1 | tee -a /home/squinlan/cliff_ai/web_server.log

# If you use Flask and want debug reloading, add FLASK_ENV:
# export FLASK_ENV=development
# python3 -m flask run --app web.cliff_server.app

