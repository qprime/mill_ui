import os
import json

CONFIG_FILE = "context_config.json"
OUTPUT_FILE = "context_dump.txt"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_config():
    with open(os.path.join(PROJECT_ROOT, CONFIG_FILE), "r") as f:
        return json.load(f)


def is_binary(file_path):
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True


def estimate_token_count(text):
    return int(len(text.split()) * 1.3)


def should_exclude(path, config):
    # Exclude if any directory in the path matches an excluded dir
    norm_path = os.path.normpath(path)
    parts = set(norm_path.split(os.sep))
    for excl in config["exclude_dirs"]:
        if excl in parts:
            return True
    return False


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


def collect_files(config):
    file_list = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Remove excluded dirs in-place by name, anywhere in path
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), config) and not d.startswith(".")]
        for f in files:
            full_path = os.path.join(root, f)
            if should_exclude(full_path, config):
                continue
            if should_include(full_path, config):
                file_list.append(full_path)
    return file_list


def generate_dump():
    config = load_config()
    files = collect_files(config)
    print(f"Found {len(files)} files for context dump")

    # Show a preview before writing
    print("\nFirst 10 files to be included:")
    for file in files[:10]:
        print("  ", os.path.relpath(file, PROJECT_ROOT))
    if len(files) > 10:
        print("  ...")

    confirm = input("\nProceed with dump? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    total_tokens = 0
    with open(os.path.join(PROJECT_ROOT, OUTPUT_FILE), "w", encoding="utf-8") as out:
        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                out.write(f"\n# === {os.path.relpath(file, PROJECT_ROOT)} ===\n")
                out.write(content + "\n")
                total_tokens += estimate_token_count(content)
            except Exception as e:
                print(f"Skipping {file}: {e}")

    print(f"\nDump complete → {OUTPUT_FILE}")
    print(f"Estimated token count: {int(total_tokens)}")


if __name__ == "__main__":
    generate_dump()
