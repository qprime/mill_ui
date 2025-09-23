from __future__ import annotations

import argparse
import json
from typing import Callable

from memories.framework.profile import profile_status, set_active_profile


def _emit_status() -> None:
    status = profile_status()
    print(json.dumps(status, indent=2))


def _apply(profile: str, *, persist: bool, seed: bool) -> int:
    set_active_profile(profile, persist=persist, seed=seed)
    _emit_status()
    return 0


def _status_cmd(_: argparse.Namespace) -> int:
    _emit_status()
    return 0


def _set_cmd(args: argparse.Namespace) -> int:
    return _apply(args.profile, persist=args.persist, seed=args.seed)


def _enable_test_cmd(args: argparse.Namespace) -> int:
    return _apply("test", persist=args.persist, seed=args.seed)


def _disable_test_cmd(args: argparse.Namespace) -> int:
    return _apply("main", persist=args.persist, seed=args.seed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory_profile", description="Manage cliff memory profiles")
    sub = parser.add_subparsers(dest="command", required=True)

    status_cmd = sub.add_parser("status", help="Show current memory profile")
    status_cmd.set_defaults(handler=_status_cmd)

    set_cmd = sub.add_parser("set", help="Set active profile")
    set_cmd.add_argument("profile", help="Profile name (e.g. main, test, dev)")
    set_cmd.add_argument("--no-seed", dest="seed", action="store_false", default=True, help="Skip seeding baseline files for new profile")
    set_cmd.add_argument("--no-persist", dest="persist", action="store_false", default=True, help="Skip writing profile selection to state file")
    set_cmd.set_defaults(handler=_set_cmd)

    enable_test_cmd = sub.add_parser("enable-test", help="Switch to the shared test profile")
    enable_test_cmd.add_argument("--no-seed", dest="seed", action="store_false", default=True)
    enable_test_cmd.add_argument("--no-persist", dest="persist", action="store_false", default=True)
    enable_test_cmd.set_defaults(handler=_enable_test_cmd)

    disable_test_cmd = sub.add_parser("disable-test", help="Return to the main profile")
    disable_test_cmd.add_argument("--no-seed", dest="seed", action="store_false", default=True)
    disable_test_cmd.add_argument("--no-persist", dest="persist", action="store_false", default=True)
    disable_test_cmd.set_defaults(handler=_disable_test_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = getattr(args, "handler")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
