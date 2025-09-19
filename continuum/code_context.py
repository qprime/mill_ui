# path: continuum/code_context.py
# type: context_builder
# tags: project, metadata, header
# owner: cliff
# depends_on: continuum/file_crawl.py
# description: Extracts metadata headers or stripped code from all project files for AI ingestion.

import argparse
import re
import os
from pathlib import Path
import json

from continuum.file_crawl import find_files

HEADER_FIELD_RE = re.compile(r'#\s*(\w+):\s*(.*)')
DEFAULT_INCLUDE_EXTENSIONS = [".py", ".js", ".yaml", ".yml"]

def scrub_whitespace(text):
    """Remove excessive whitespace from text."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.replace("\r\n", "\n").replace("\r", "\n")

def strip_non_header_comments_and_docstrings(code):
    """Remove comments and docstrings from code, but preserve structure."""
    out_lines = []
    in_docstring = False
    docstring_delim = None
    lines = code.splitlines()
    
    for line in lines:
        stripped = line.strip()
        if not in_docstring:
            # Check for docstring start
            if (stripped.startswith('"""') or stripped.startswith("'''")):
                # Single-line docstring
                if (stripped.count('"""') == 2 or stripped.count("'''") == 2) and len(stripped) > 6:
                    continue
                # Multi-line docstring start
                in_docstring = True
                docstring_delim = stripped[:3]
                continue
            # Skip comment lines
            if stripped.startswith("#"):
                continue
            # Remove inline comments but preserve the code
            line_no_trail_comment = re.sub(r'(?<!["\'])#.*', '', line)
            out_lines.append(line_no_trail_comment.rstrip())
        else:
            # Check for docstring end
            if docstring_delim and docstring_delim in stripped:
                in_docstring = False
                docstring_delim = None
            continue
    
    code_no_comments = "\n".join(out_lines)
    return scrub_whitespace(code_no_comments)

def count_tokens(text: str, model_name: str = "gpt-4.1"):
    """Count tokens in text using the specified model's tokenizer."""
    try:
        import tiktoken  # local import to avoid hard dependency at module import time

        try:
            enc = tiktoken.encoding_for_model(model_name)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # If tokenizer is unavailable, return a simple whitespace token count as fallback
        return len(text.split())

def generate_code_context(
    root_dir: str,
    mode: str = "code",
    model_name: str = "gpt-4.1"
):
    root_path = Path(root_dir).resolve()
    files = find_files(root_path, allowed_ext=DEFAULT_INCLUDE_EXTENSIONS)
    blocks = []
    stats = []
    
    for file_path in files:
        try:
            file_abs = Path(file_path).resolve()
            # Robust relative path (works even if file_abs isn't strictly under root_path)
            rel_path = os.path.relpath(str(file_abs), start=str(root_path))
        except Exception:
            # Fallback: just use the name
            rel_path = Path(file_path).name

        try:
            with open(file_abs, 'r', encoding='utf-8') as f:
                lines = []
                first_line = True
                
                for line in f:
                    # If first line isn't a comment, skip this file (no header)
                    if first_line:
                        if not line.strip().startswith("#"):
                            break
                        first_line = False
                    
                    # Collect header lines (those starting with #)
                    if line.strip().startswith("#"):
                        lines.append(line)
                    else:
                        # Hit first non-header line
                        if mode == "metadata":
                            # In metadata mode, we're done - we got the header
                            break
                        else:
                            # In code mode, reset and start collecting code
                            lines = []
                            lines.append(line)  # Include this first non-header line
                            # Read the rest of the file
                            for remaining_line in f:
                                lines.append(remaining_line)
                            break
                
                # Skip if no content collected
                if not lines:
                    continue
                
                # Process based on mode
                if mode == "metadata":
                    # Output header block with a blank line separator so downstream parsers can split blocks.
                    block = "".join(lines).rstrip() + "\n\n"
                else:  # code mode
                    # Process the code (strip comments/docstrings, clean whitespace)
                    code = "".join(lines)
                    code = strip_non_header_comments_and_docstrings(code)
                    code = scrub_whitespace(code)
                    if not code.strip():
                        continue
                    # Prepend file marker in code mode
                    block = f"### FILE: {rel_path} ###\n{code.strip()}\n"
                
                blocks.append(block)
                size = len(block.encode("utf-8"))
                tokens = count_tokens(block, model_name=model_name)
                stats.append((rel_path, size, tokens))
                
        except (OSError, UnicodeDecodeError):
            continue
    
    return "".join(blocks), stats

def print_stats(stats):
    """Print statistics about processed files."""
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
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory to scan.")
    parser.add_argument("-o", "--output", help="Write result to this file (default: none)")
    parser.add_argument("--mode", choices=["code", "metadata"], default="code", 
                       help="Extraction mode: code or metadata")
    parser.add_argument("--model-name", default="gpt-4.1")
    args = parser.parse_args()

    result, stats = generate_code_context(
        root_dir=args.root_dir,
        mode=args.mode,
        model_name=args.model_name,
    )

    if args.output and result:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)

    print_stats(stats)

if __name__ == "__main__":
    main()
