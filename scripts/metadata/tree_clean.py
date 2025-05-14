import os

EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "models", "chroma_store", "node_modules"}
MAX_DEPTH = 3

def print_tree(start_path=".", prefix="", depth=0):
    if depth > MAX_DEPTH:
        return

    try:
        entries = sorted(
            [e for e in os.listdir(start_path) if e not in EXCLUDE_DIRS],
            key=lambda x: (not os.path.isdir(os.path.join(start_path, x)), x.lower())
        )
    except PermissionError:
        return

    for i, entry in enumerate(entries):
        path = os.path.join(start_path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(f"{prefix}{connector}{entry}")
        if os.path.isdir(path):
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(path, prefix + extension, depth + 1)

if __name__ == "__main__":
    print_tree(".")
