import json
import argparse
import ast
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from scripts.utils.ai_router import get_router

CHUNK_DIR = PROJECT_ROOT / "memory" / "development" / "code_chunks"
ANNOTATED_DIR = PROJECT_ROOT / "memory" / "development" / "annotated_chunks"
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

def annotate_function_chunk(chunk, router, model):
    if chunk["type"] == "preamble":
        return chunk["code"]  # no annotation for preamble

    prompt = f'''
You are an expert Python developer and documentation specialist.
You will annotate the following function or class with a structured Python docstring.

Use this exact format:
"""
@cliff.function_purpose: What this function or class does
@cliff.side_effects: Any file, network, or system effects (or None)
@cliff.returns: What is returned, if anything
"""

Insert the docstring directly inside the function/class.

Here is the code:

{chunk["code"]}

---
Return valid Python only. Do not include markdown. Do not return explanations or commentary.
'''

    messages = [
        {"role": "system", "content": "You annotate Python code for AI consumption using structured docstrings."},
        {"role": "user", "content": prompt}
    ]

    result = router.chat(messages, model=model).strip()

    # Strip Markdown fences if present
    if result.startswith("```python"):
        result = result.removeprefix("```python").removesuffix("```")

    return result.strip()

def is_valid_python(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

def inject_docstring(original_code, docstring):
    lines = original_code.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("def ") or line.strip().startswith("class "):
            indent = len(line) - len(line.lstrip()) + 4
            indent_space = " " * indent
            doc_lines = [f'{indent_space}{l}' if l else '' for l in docstring.strip().splitlines()]
            return "\n".join(lines[:i+1] + doc_lines + lines[i+1:])
    return original_code

def process_chunk_file(json_path, router, model, dry_run=False):
    json_path = json_path.resolve()
    with open(json_path, "r") as f:
        chunks = json.load(f)

    annotated = []
    for chunk in chunks:
        annotated_code = annotate_function_chunk(chunk, router, model)

        if chunk["type"] != "preamble" and not is_valid_python(annotated_code):
            print(f"⚠️ Invalid syntax in annotated {chunk['name']} — falling back to injection")
            docstring = annotated_code.strip().split("\n")[:5]  # crude slice to get only the doc block
            injected = inject_docstring(chunk["code"], "\n".join(docstring))
            final_code = injected if is_valid_python(injected) else chunk["code"]
        else:
            final_code = annotated_code

        annotated.append({**chunk, "annotated_code": final_code})
        print(f"✅ Annotated {chunk['type']} {chunk.get('name', '')} from {chunk['file']}")

    out_path = ANNOTATED_DIR / json_path.relative_to(CHUNK_DIR)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        for a in annotated:
            print("\n--- Preview ---\n", a["annotated_code"][:500], "...\n")
    else:
        with open(out_path, "w") as f:
            json.dump(annotated, f, indent=2)
        print(f"💾 Wrote {len(annotated)} annotated chunks to {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="Path to a single chunk .json file")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo", choices=["gpt-3.5-turbo", "gpt-4"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    router = get_router("openai")
    process_chunk_file(Path(args.file), router, args.model, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
