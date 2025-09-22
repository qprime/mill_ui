from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class OperateCommand:
    """Describes a predefined operations command sequence."""

    id: str
    title: str
    description: str
    commands: List[List[str]]


def sh(cmd: str) -> List[str]:
    return ["bash", "-lc", cmd]


OPERATE_ACTIONS: Dict[str, OperateCommand] = {
    "status.cpu_ram_uptime": OperateCommand(
        id="status.cpu_ram_uptime",
        title="CPU/RAM/Uptime",
        description="Show CPU load, memory usage, and uptime",
        commands=[sh("echo '--- CPU ---'"), sh("uptime"), sh("echo '\n--- Memory ---'"), sh("free -h"), sh("echo '\n--- Top (head) ---'"), sh("ps aux --sort=-%mem | head -n 10")],
    ),
    "status.disk": OperateCommand(
        id="status.disk",
        title="Disk Usage",
        description="List mounted disks and usage",
        commands=[sh("df -h"), sh("echo '\nInodes'"), sh("df -hi")],
    ),
    "status.network": OperateCommand(
        id="status.network",
        title="Network Summary",
        description="Show IP configuration and listening ports",
        commands=[sh("ip addr"), sh("echo '\nListening sockets'"), sh("ss -tulpn")],
    ),
    "packages.apt_list": OperateCommand(
        id="packages.apt_list",
        title="APT Packages",
        description="List top-level apt packages",
        commands=[sh("apt list --installed")],
    ),
    "services.list": OperateCommand(
        id="services.list",
        title="Systemd Services",
        description="List running user and system services",
        commands=[sh("systemctl --user list-units --type=service"), sh("echo '\n-- System --'"), sh("systemctl list-units --type=service")],
    ),
    "docker.ps": OperateCommand(
        id="docker.ps",
        title="Docker Containers",
        description="Show docker containers",
        commands=[sh("docker ps"), sh("echo '\nImages'"), sh("docker images")],
    ),
    "git.status": OperateCommand(
        id="git.status",
        title="Git Status",
        description="Show git status and recent commits",
        commands=[sh("git status"), sh("echo '\nLast commits'"), sh("git log -5 --oneline")],
    ),
    "logs.syslog_tail": OperateCommand(
        id="logs.syslog_tail",
        title="Tail Syslog",
        description="Tail system journal",
        commands=[sh("journalctl -n 200 --no-pager")],
    ),
    "files.recent": OperateCommand(
        id="files.recent",
        title="Recent Files",
        description="List recently modified files in workspace",
        commands=[sh("ls -alt | head")],
    ),
}


__all__ = ["OperateCommand", "OPERATE_ACTIONS"]
