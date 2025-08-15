# path: cam_generator/__main__.py
# desc: Module entry point delegating to CLI
# api: main
# tags: cli,entry

from __future__ import annotations

from cam_generator.cli import run_cli

__all__ = ["main"]


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
