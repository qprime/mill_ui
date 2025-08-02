"""
Extracts codebase context for LLM injection. Supports full code, docstrings, or function/class signatures only.
"""


import os
import argparse
import re
import tiktoken

DEFAULT_INCLUDE_EXTENSIONS = ('.py', '.js', '.yaml', '.yml')
DEFAULT_EXCLUDE_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'tests'}

def should_include_file(filename, include_exts=DEFAULT_INCLUDE_EXTENSIONS):
    return filename.endswith(include_exts)

def should_exclude_dir(dirname):
    return dirname in DEFAULT_EXCLUDE_DIRS

def scrub_whitespace(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.replace('\r\n', '\n').replace('\r', '\n')

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
            return text[:end+3]
    return ""

def generate_context(
    root_dir,
    include_exts=DEFAULT_INCLUDE_EXTENSIONS,
    exclude_dirs=DEFAULT_EXCLUDE_DIRS,
    scrub=True,
    file_filter=None,
    stats_list=None,
    docstrings_only=False,
    function_signatures=False
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

            if function_signatures and fname.endswith('.py'):
                display_text = get_function_signatures(text)
            elif docstrings_only and fname.endswith('.py'):
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
        description="Generate concatenated codebase context for CLIFF or LLM ingestion."
    )
    parser.add_argument(
        "root_dir",
        help="Root directory of the codebase to scan.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write result to this file (default: stdout)",
    )
    parser.add_argument(
        "--no-scrub",
        action="store_true",
        help="Disable whitespace normalization/scrubbing (default: scrub whitespace)."
    )
    parser.add_argument(
        "--docstrings-only",
        action="store_true",
        help="Include only the top-level docstring of each Python file."
    )
    parser.add_argument(
        "--function-signatures",
        action="store_true",
        help="Include only function/class signatures (+ first docstring, if present) in each Python file."
    )
    args = parser.parse_args()

    stats = []
    context = generate_context(
        args.root_dir,
        scrub=not args.no_scrub,
        stats_list=stats,
        docstrings_only=args.docstrings_only,
        function_signatures=args.function_signatures,
    )
    print_stats(stats)
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as out:
            out.write(context)
        print(f"[INFO] Context written to {args.output}")
    else:
        print(context)

if __name__ == "__main__":
    main()
