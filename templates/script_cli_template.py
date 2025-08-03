# path: templates/script_cli_template.py
# type: CLI utility
# tags: cli, template, argparse, script
# owner: cliff
# depends_on: argparse
# description: Template for command-line interface scripts using argparse.

import argparse


def main():
    parser = argparse.ArgumentParser(description="[What this script does]")

    args = parser.parse_args()


if __name__ == "__main__":
    main()
