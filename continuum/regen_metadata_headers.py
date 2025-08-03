# path: continuum/regen_metadata_headers.py
# type: metadata utility
# tags: metadata, regeneration, headers, script
# owner: cliff
# depends_on: ai_core.client,continuum.file_crawl
# description: Regenerates metadata headers for Python files to facilitate AI context selection.

import os
import re
import sys
import shutil
from pathlib import Path

from ai_core import client
from continuum.file_crawl import find_relative_files

BACKUP_SUFFIX = '.bak'

GPT_PROMPT = """
Given the following Python file, generate a concise, structured metadata header for AI context selection.

The header must include:
- path: repo-relative path to the file
- type: a 1–3 word summary of the file’s purpose/role
- tags: comma-separated keywords (e.g., persona, cam, context, image, test, utils)
- owner: 'cliff'
- depends_on: main file/module dependencies (files imported by this module, if any)
- description: a 1-line, purpose-focused description for LLM context selection (not for humans)

The header should be at the very top, formatted as plain # key: value lines.

Do NOT regenerate the code body, only return the header block.

Example:
# path: ai_core/personas/styles.py
# type: persona_styles_module
# tags: persona, style, cam, config_loader
# owner: cliff
# depends_on: ai_core/personas/personas_manager.py
# description: Loads CAM style configs for persona prompting. Used by image generator.
"""

def strip_top_header(code):
    """
    Remove contiguous top-of-file comments (# ...) or triple-quoted strings.
    Returns (old_header, code_body).
    """
    header_lines = []
    lines = code.splitlines(keepends=True)
    i = 0
    in_docstring = False

    while i < len(lines):
        line = lines[i]
        if i == 0 and re.match(r'^\s*["\']{3}', line):
            # Triple-quoted string at very top
            quote = line.strip()[:3]
            in_docstring = True
            header_lines.append(line)
            i += 1
            while i < len(lines):
                header_lines.append(lines[i])
                if lines[i].strip().endswith(quote):
                    i += 1
                    break
                i += 1
        elif line.lstrip().startswith('#'):
            header_lines.append(line)
            i += 1
        elif line.strip() == '':
            header_lines.append(line)
            i += 1
        else:
            break
    return ''.join(header_lines), ''.join(lines[i:])

def get_llm_header(file_path, code_body):
    prompt = GPT_PROMPT + f"\nRepo path: {file_path}\n\nCode:\n{code_body[:8000]}"
    messages = [
        {"role": "system", "content": "You are an expert Python toolmaker."},
        {"role": "user", "content": prompt}
    ]
    result = client.get_chat_completion(messages, model="gpt-4-1106-preview")
    header_lines = [l for l in result.splitlines() if l.strip().startswith("#")]
    return '\n'.join(header_lines) + '\n\n'

def backup_file(path):
    backup = str(path) + BACKUP_SUFFIX
    shutil.copy2(path, backup)

def should_skip(path, skip_inits=True):
    """Return True if file should be skipped (e.g. __init__.py and skip_inits is True)."""
    return skip_inits and Path(path).name == "__init__.py"

def update_single_file(
    file_path,
    root=".",
    dry_run=False,
    backup=True,
    print_only=False,
    skip_inits=True,
    force=False,
):
    abs_path = os.path.abspath(file_path)
    rel_path = os.path.relpath(abs_path, root)
    if should_skip(abs_path, skip_inits):
        print(f"[SKIP] {rel_path}: Skipped __init__.py")
        return
    with open(abs_path, "r", encoding="utf-8") as f:
        code = f.read()
    old_header, code_body = strip_top_header(code)
    new_header = get_llm_header(rel_path, code_body)
    # Only skip if not forcing
    if not force and new_header.strip() == old_header.strip():
        print(f"[SKIP] {rel_path}: Header unchanged")
        return
    if dry_run or print_only:
        print(f"\n--- {rel_path} ---\n{new_header}{code_body[:200]}...")
    else:
        if backup:
            backup_file(abs_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_header)
            f.write(code_body)
        print(f"[UPDATED] {rel_path}")

def update_metadata_headers(
    root=".",
    dry_run=False,
    backup=True,
    print_only=False,
    skip_inits=True,
    force=False,
    file_path=None
):
    """Update headers in all Python files (or one file if file_path is set)."""
    if file_path:
        update_single_file(
            file_path=file_path,
            root=root,
            dry_run=dry_run,
            backup=backup,
            print_only=print_only,
            skip_inits=skip_inits,
            force=force,
        )
        return

    py_files = find_relative_files(Path(root), allowed_ext=['.py'])
    for rel_path in py_files:
        if should_skip(rel_path, skip_inits):
            print(f"[SKIP] {rel_path}: Skipped __init__.py")
            continue
        update_single_file(
            file_path=os.path.join(root, rel_path),
            root=root,
            dry_run=dry_run,
            backup=backup,
            print_only=print_only,
            skip_inits=skip_inits,
            force=force,
        )

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate metadata headers for .py files in the project.")
    parser.add_argument('--root', type=str, default='.', help='Project root (default: current dir)')
    parser.add_argument('--file', type=str, default=None, help='Update only a single Python file (relative or absolute path)')
    parser.add_argument('--dry-run', action='store_true', help='Print changes, do not write files')
    parser.add_argument('--no-backup', action='store_true', help='Do not create .bak backups')
    parser.add_argument('--print-only', action='store_true', help='Only print headers+snippets, do not modify files')
    parser.add_argument('--include-inits', action='store_true', help='Update __init__.py files (normally skipped)')
    parser.add_argument('--force', action='store_true', help='Regenerate header even if unchanged')
    args = parser.parse_args()

    update_metadata_headers(
        root=args.root,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        print_only=args.print_only,
        skip_inits=not args.include_inits,
        force=args.force,
        file_path=args.file,
    )

if __name__ == "__main__":
    main()
