"""
[local services]
TODO: describe module functionality.
"""

import os
import json
from pathlib import Path
from datetime import datetime

CLI_LOG_PATH = Path("memory/cliff_state/cli_logs.jsonl")


def save_cli_logs(logs: list[dict]):
    CLI_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CLI_LOG_PATH.open("a", encoding="utf-8") as f:
        for entry in logs:
            json.dump(entry, f)
            f.write("\n")
