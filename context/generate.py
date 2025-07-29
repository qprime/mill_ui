"""
Generates unified context dumps and file lists for the CLIFF AI repo.
"""

import os
import sys
import subprocess
import json
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONTEXT_DIR = os.path.join(PROJECT_ROOT, "context", "generated")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "context", "config.json")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def git_ls_files():
    files = subprocess.check_output(
        ["git", "ls-files"], cwd=PROJECT_ROOT, encoding="utf-8"
    ).splitlines()
    return [os.path.join(PROJECT_ROOT, f) for f in files]

def walk_files(config):
    file_list = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in config["exclude_dirs"] and not d.startswith(".")]
        for f in files:
            full_path = os.path.join(root, f)
            if should_include(full_path, config):
                file_list.append(full_path)
    return file_list

def is_binary(file_path):
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True

def should_include(file_path, config):
    if not os.path.isfile(file_path):
        return False
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in config["include_extensions"]:
        return False
    if os.path.getsize(file_path) > config["max_file_size_kb"] * 1024:
        return False
    for pattern in config["exclude_patterns"]:
        if pattern.startswith("*") and file_path.endswith(pattern[1:]):
            return False
    if is_binary(file_path):
        return False
    return True

def ensure_context_dir():
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    return CONTEXT_DIR

def module_full(file_list, output_path):
    total_tokens = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for file in file_list:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                out.write(f"\n# === {os.path.relpath(file, PROJECT_ROOT)} ===\n")
                out.write(content + "\n")
                total_tokens += int(len(content.split()) * 1.3)
            except Exception as e:
                print(f"Skipping {file}: {e}")
    print(f"[+] Full context written to {output_path}")
    print(f"    Estimated tokens: {total_tokens}")

def module_filestructure(file_list, output_path):
    rel_paths = [os.path.relpath(f, PROJECT_ROOT) for f in file_list]
    rel_paths.sort()
    with open(output_path, "w", encoding="utf-8") as out:
        for path in rel_paths:
            out.write(path + "\n")
    print(f"[+] File structure written to {output_path}")

def module_readmes(file_list, output_path):
    readmes = [f for f in file_list if os.path.basename(f).lower().startswith("readme") and f.lower().endswith(".md")]
    if not readmes:
        print("No README.md files found.")
    with open(output_path, "w", encoding="utf-8") as out:
        for file in readmes:
            out.write(f"\n# === {os.path.relpath(file, PROJECT_ROOT)} ===\n")
            with open(file, "r", encoding="utf-8") as f:
                out.write(f.read() + "\n")
    print(f"[+] README.md files written to {output_path}")

MODULES = {
    "full": module_full,
    "filestructure": module_filestructure,
    "readmes": module_readmes,
}

def collect_files(mode, config):
    if mode == "git":
        all_files = git_ls_files()
        return [f for f in all_files if should_include(f, config)]
    elif mode == "walk":
        return walk_files(config)
    else:
        raise ValueError(f"Unknown mode: {mode}")

def main():
    parser = argparse.ArgumentParser(description="Unified context dump for Cliff AI repo.")
    parser.add_argument("--mode", type=str, choices=["git", "walk"], default="git", help="Source mode for file collection")
    parser.add_argument("--modules", type=str, default="full", help="Comma-separated output modules: full,filestructure,readmes")
    parser.add_argument("--output", type=str, help="Output file (default: context/generated/{module}_context.txt)")
    args = parser.parse_args()

    config = load_config()
    ensure_context_dir()
    file_list = collect_files(args.mode, config)
    print(f"Found {len(file_list)} files with mode '{args.mode}'.")

    for module in args.modules.split(","):
        mod = module.strip()
        if mod not in MODULES:
            print(f"Unknown module: {mod}. Skipping.")
            continue
        out_file = args.output or os.path.join(CONTEXT_DIR, f"{mod}_context.txt")
        MODULES[mod](file_list, out_file)

if __name__ == "__main__":
    main()
