# path: continuum/code_context.py
# type: context_header_extractor
# tags: code_context, metadata, file_headers, file_crawl
# owner: cliff
# depends_on: continuum/file_crawl.py
# description: Extracts and aggregates all top-of-file metadata headers for LLM-based context selection.

import re
import json
from pathlib import Path
from continuum.file_crawl import find_files

HEADER_FIELD_RE = re.compile(r'#\s*(\w+):\s*(.*)')

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

def collect_all_headers():
   
    py_files = find_files(Path('.'), allowed_ext=['.py'])
    results = []
    for p in py_files:
        meta = extract_metadata_header(p)
        if meta:
            results.append({"path": str(p), "header": meta})
    return results

if __name__ == "__main__":
    headers = collect_all_headers()
    # Print each file's header (or output as JSON)
    print(json.dumps(headers, indent=2, sort_keys=True))
