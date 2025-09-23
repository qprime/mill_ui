# name: cli.py
# path: services/cli.py
# role: Command-line interface for managing cliff system services
# deps: argparse, pathlib, subprocess, typing, services.registry
# inputs: argv
# outputs: exit code

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List

from services.registry import Service, ServiceRegistry, load as load_registry

__all__ = ["api"]


def _systemctl_args(scope: str) -> List[str]:
    if scope == "system":
        prefix = ["sudo"] if os.geteuid() != 0 else []
        return prefix + ["systemctl"]
    return ["systemctl", "--user"]


def _run_command(args: List[str]) -> int:
    result = subprocess.run(args, check=False)
    return result.returncode


def _copy_unit(service: Service, scope: str) -> Path:
    if service.unit_file is None:
        raise RuntimeError(f"Service '{service.id}' does not define a unit_file")
    data = service.unit_file.read_text(encoding="utf-8")
    if scope == "system":
        target_dir = Path("/etc/systemd/system")
        target = target_dir / service.unit
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            subprocess.run(
                ["sudo", "install", "-d", "-m", "755", str(target_dir)],
                check=True,
            )
            subprocess.run(
                ["sudo", "install", "-m", "644", str(tmp_path), str(target)],
                check=True,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        return target

    target_dir = Path.home() / ".config/systemd/user"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / service.unit
    target.write_text(data, encoding="utf-8")
    return target


def _remove_unit(service: Service, scope: str) -> None:
    if scope == "system":
        target = Path("/etc/systemd/system") / service.unit
        subprocess.run(["sudo", "rm", "-f", str(target)], check=False)
        return
    else:
        target = Path.home() / ".config/systemd/user" / service.unit
    if target.exists():
        target.unlink()


def _list_services(registry: ServiceRegistry) -> None:
    for svc in registry.all():
        print(f"{svc.id:18} {svc.unit:28} {svc.description}")


def _status(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["status", service.unit]
    return _run_command(args)


def _start(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["start", service.unit]
    return _run_command(args)


def _stop(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["stop", service.unit]
    return _run_command(args)


def _restart(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["restart", service.unit]
    return _run_command(args)


def _enable(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["enable", service.unit]
    return _run_command(args)


def _disable(service: Service, scope: str) -> int:
    args = _systemctl_args(scope) + ["disable", service.unit]
    return _run_command(args)


def _install(service: Service, scope: str) -> int:
    target = _copy_unit(service, scope)
    print(f"Installed unit file to {target}")
    _run_command(_systemctl_args(scope) + ["daemon-reload"])
    return 0


def _uninstall(service: Service, scope: str) -> int:
    _remove_unit(service, scope)
    print(f"Removed unit file for {service.id}")
    _run_command(_systemctl_args(scope) + ["daemon-reload"])
    return 0


def _update(service: Service, scope: str) -> int:
    rc = _install(service, scope)
    if rc != 0:
        return rc
    return _restart(service, scope)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="services")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List available services")
    list_cmd.add_argument("--scope", choices=["user", "system"], default=None)

    service_commands: Iterable[str] = [
        "status",
        "start",
        "stop",
        "restart",
        "enable",
        "disable",
        "install",
        "uninstall",
        "update",
    ]

    for name in service_commands:
        cmd = sub.add_parser(name, help=f"{name.title()} a service")
        cmd.add_argument("service", help="Service id from registry")
        cmd.add_argument("--scope", choices=["user", "system"], default=None)

    return parser


def _determine_scope(service: Service, override: str | None) -> str:
    if override:
        return override
    return service.scope


def api(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = load_registry()

    if args.command == "list":
        _list_services(registry)
        return 0

    service = registry.get(args.service)
    scope = _determine_scope(service, getattr(args, "scope", None))

    if args.command == "status":
        return _status(service, scope)
    if args.command == "start":
        return _start(service, scope)
    if args.command == "stop":
        return _stop(service, scope)
    if args.command == "restart":
        return _restart(service, scope)
    if args.command == "enable":
        return _enable(service, scope)
    if args.command == "disable":
        return _disable(service, scope)
    if args.command == "install":
        return _install(service, scope)
    if args.command == "uninstall":
        return _uninstall(service, scope)
    if args.command == "update":
        return _update(service, scope)

    return 0


def main() -> int:
    return api()


if __name__ == "__main__":
    raise SystemExit(main())
