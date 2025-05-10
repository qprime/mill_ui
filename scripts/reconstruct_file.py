import argparse
import difflib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = PROJECT_ROOT / "memory" / "development" / "code_chunks"
ANNOTATED_DIR = PROJECT_ROOT / "memory" / "development" / "annotated_chunks"
REBUILT_DIR = PROJECT_ROOT / "memory" / "development" / "reconstructed"
DIFF_DIR = PROJECT_ROOT / "memory" / "development" / "reconstructed_diffs"

REBUILT_DIR.mkdir(parents=True, exist_ok=True)
DIFF_DIR.mkdir(parents=True, exist_ok=True)

def load_original(chunks_path):
    code_path = CHUNK_DIR / chunks_path.relative_to(ANNOTATED_DIR)
    with open(code_path, "r") as f:
        return json.load(f)

def load_annotated(chunks_path):
    with open(chunks_path, "r") as f:
        return json.load(f)

def reconstruct_file(annotated_chunks):
    return "\n\n".join(chunk["annotated_code"] for chunk in annotated_chunks if chunk.get("annotated_code")) + "\n"

def compare_to_original(annotated_chunks, original_chunks):
    annotated = [chunk.get("annotated_code", "") for chunk in annotated_chunks]
    original = [chunk.get("code", "") for chunk in original_chunks]
    annotated_text = "\n\n".join(annotated)
    original_text = "\n\n".join(original)
    diff = list(difflib.unified_diff(
        original_text.splitlines(),
        annotated_text.splitlines(),
        fromfile='original',
        tofile='annotated',
        lineterm=''  # no extra newlines
    ))
    return "\n".join(diff)

def write_diff(diff_text, target_path):
    diff_file = DIFF_DIR / (target_path.stem + ".diff")
    with open(diff_file, "w") as f:
        f.write(diff_text)
    print(f"📝 Diff written to: {diff_file}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotated", required=True, help="Path to annotated chunk file")
    parser.add_argument("--compare", action="store_true", help="Also compare with original and write diff")
    args = parser.parse_args()

    chunks_path = Path(args.annotated).resolve()
    annotated_chunks = load_annotated(chunks_path)
    rebuilt_code = reconstruct_file(annotated_chunks)

    target_path = REBUILT_DIR / chunks_path.with_suffix(".py").name
    with open(target_path, "w") as f:
        f.write(rebuilt_code)
    print(f"✅ Reconstructed file written to: {target_path}")

    if args.compare:
        original_chunks = load_original(chunks_path)
        diff_text = compare_to_original(annotated_chunks, original_chunks)
        write_diff(diff_text, target_path)

if __name__ == "__main__":
    main()
