"""
[local services]
TODO: describe module functionality.
"""

import os
import sys
import socket
import subprocess
import json
from datetime import datetime, timezone

try:
    UTC = datetime.UTC
except AttributeError:
    UTC = timezone.utc

SESSION_FILE = os.path.expanduser("~/.cliff_session_id")
HEARTBEAT_FILE = os.path.expanduser("~/.cliff_cli_heartbeat")

MY_HOSTNAME = socket.gethostname()

if MY_HOSTNAME == "EQBeelink1":
    SERVER_URL = "http://localhost:5050/cli-logs"
else:
    SERVER_URL = "http://EQBeelink1.local:5050/cli-logs"


def get_session_id():
    if not os.path.exists(SESSION_FILE):
        hostname = socket.gethostname()
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        session_id = f"{hostname }-{timestamp }"
        with open(SESSION_FILE, "w") as f:
            f.write(session_id)
        return session_id
    else:
        with open(SESSION_FILE, "r") as f:
            return f.read().strip()


def update_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(datetime.now(UTC).isoformat())
    except Exception as e:
        print(f"[CLI Logger] Heartbeat error: {e }", file=sys.stderr)


def log_command(cmd):
    try:
        hostname = socket.gethostname()
        session_id = get_session_id()
        update_heartbeat()
        command_record = {
            "hostname": hostname,
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "command": cmd.strip(),
        }
        payload = {"logs": [command_record]}

        subprocess.run(
            [
                "curl",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
                SERVER_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[CLI Logger] Logging error: {e }", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        print(f"Logged and pushed: {command }")
        log_command(command)
