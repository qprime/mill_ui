# path: continuum/code_context.py
# type: context_generator
# tags: metadata, header, token, count, utils
# owner: cliff
# depends_on: tiktoken, pathlib, argparse, os, json, re
# description: Generates structured context and token stats from the codebase for AI ingestion.

import os
import argparse
import re
import json
from pathlib import Path
import tiktoken

# Modern header extraction regex (from your latest version)
HEADER_FIELD_RE = re.compile(r'#\s*(\w+):\s*(.*)')

DEFAULT_INCLUDE_EXTENSIONS = (".py", ".js", ".yaml", ".yml")
DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", "venv", ".venv", "tests"}

def should_include_file(filename, include_exts=DEFAULT_INCLUDE_EXTENSIONS):
    return filename.endswith(include_exts)

def should_exclude_dir(dirname):
    return dirname in DEFAULT_EXCLUDE_DIRS

def scrub_whitespace(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.replace("\r\n", "\n").replace("\r", "\n")

def count_tokens(text: str, model_name: str = "gpt-4.1"):
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def get_function_signatures(text):
    lines = text.splitlines()
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            output.append(line.rstrip())
    return "\n".join(output)

def get_top_level_docstring(text):
    text = text.lstrip()
    if text.startswith('"""') or text.startswith("'''"):
        triple = text[:3]
        end = text.find(triple, 3)
        if end != -1:
            return text[: end + 3]
    return ""

# --- Modern metadata header extraction (from your latest code) ---

def extract_metadata_header(path: Path):
    meta = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip().startswith("#"):
                    break  # Stop at first code/import
                m = HEADER_FIELD_RE.match(line)
                if m:
                    key, value = m.group(1).lower(), m.group(2).strip()
                    if key == "tags":
                        meta[key] = [t.strip() for t in value.split(",")]
                    else:
                        meta[key] = value
            return meta
    except Exception:
        return {}

def collect_all_headers(root_dir, include_exts=(".py",)):
    results = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]
        for fname in filenames:
            if should_include_file(fname, include_exts):
                path = os.path.join(dirpath, fname)
                meta = extract_metadata_header(Path(path))
                if meta:
                    results.append({"path": str(path), "header": meta})
    return results


# --- End metadata header logic ---

def generate_context(
    root_dir,
    include_exts=DEFAULT_INCLUDE_EXTENSIONS,
    exclude_dirs=DEFAULT_EXCLUDE_DIRS,
    scrub=True,
    file_filter=None,
    stats_list=None,
    docstrings_only=False,
    function_signatures=False,
):
    parts = []
    stats = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]
        for fname in sorted(filenames):
            if not should_include_file(fname, include_exts):
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root_dir)
            if file_filter and not file_filter(rel_path):
                continue
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                print(f"[WARN] Failed to read {rel_path}: {e}")
                continue

            if function_signatures and fname.endswith(".py"):
                display_text = get_function_signatures(text)
            elif docstrings_only and fname.endswith(".py"):
                display_text = get_top_level_docstring(text)
            elif docstrings_only:
                display_text = ""
            else:
                display_text = text
                if scrub:
                    display_text = scrub_whitespace(display_text)

            size = len(display_text.encode("utf-8"))
            tokens = count_tokens(display_text)
            stats.append((rel_path, size, tokens))
            if display_text.strip():
                parts.append(f"### FILE: {rel_path} ###\n{display_text}\n")

    if stats_list is not None:
        stats_list.extend(stats)
    return "\n".join(parts)

def print_stats(stats):
    file_count = len(stats)
    total_bytes = sum(size for _, size, _ in stats)
    total_tokens = sum(tokens for _, _, tokens in stats)
    print(f"[STATS] Files included: {file_count}")
    print(f"[STATS] Total size: {total_bytes} bytes")
    print(f"[STATS] Estimated total tokens: {total_tokens}")
    print(f"[STATS] Top 5 largest files:")
    for rel_path, size, tokens in sorted(stats, key=lambda x: -x[1])[:5]:
        print(f"  {rel_path} | {size} bytes | {tokens} tokens")

def main():
    parser = argparse.ArgumentParser(
        description="Generate concatenated codebase context or metadata headers for CLIFF or LLM ingestion."
    )
    parser.add_argument(
        "root_dir",
        help="Root directory of the codebase to scan.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write result to this file (default: stdout)",
    )
    parser.add_argument(
        "--no-scrub",
        action="store_true",
        help="Disable whitespace normalization/scrubbing (default: scrub whitespace).",
    )
    parser.add_argument(
        "--docstrings-only",
        action="store_true",
        help="Include only the top-level docstring of each Python file.",
    )
    parser.add_argument(
        "--function-signatures",
        action="store_true",
        help="Include only function/class signatures (+ first docstring, if present) in each Python file.",
    )
    parser.add_argument(
        "--headers-only",
        action="store_true",
        help="Extract only the modern metadata headers (JSON).",
    )
    args = parser.parse_args()

    if args.headers_only:
        # Use modern header extractor, output JSON
        headers = collect_all_headers(args.root_dir)
        output = json.dumps(headers, indent=2, sort_keys=True)
        stats = None
    else:
        stats = []
        output = generate_context(
            args.root_dir,
            scrub=not args.no_scrub,
            stats_list=stats,
            docstrings_only=args.docstrings_only,
            function_signatures=args.function_signatures,
        )

    if stats:
        print_stats(stats)
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as out:
            out.write(output)
        print(f"[INFO] Context written to {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()
