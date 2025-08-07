# path: local_services/cli_archiver/server/cli_log_store.py
# type: log storage module
# tags: cli, archive, server, jsonl, log
# owner: cliff
# depends_on: os, json, pathlib, datetime
# description: Persists CLI logs to a JSON lines file on server side.

import os
import json
from pathlib import Path
from datetime import datetime

CLI_LOG_PATH = Path("memoriescliff_state/cli_logs.jsonl")


def save_cli_logs(logs: list[dict]):
    CLI_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CLI_LOG_PATH.open("a", encoding="utf-8") as f:
        for entry in logs:
            json.dump(entry, f)
            f.write("\n")
