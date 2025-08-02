"""
[pipeline]
TODO: describe module functionality.
"""

import os

OUTPUT_FILE = "project_dump.txt"
PYTHON_HEADER = "# === PYTHON FILES ===\n\n"
YAML_HEADER = "\n\n# === YAML FILES ===\n\n"


ALLOWED_DIRS = {
    ".",
    "analysis",
    "config",
    "core",
    "gcode",
    "optimizers",
    "path_builders",
    "pocket_holer",
    "prompt_templates",
    "visualization",
    "viewer",
}


ALLOWED_DIRS = {os.path.normpath(d) for d in ALLOWED_DIRS}


def is_allowed(path):
    parts = os.path.normpath(path).split(os.sep)
    return parts[0] in ALLOWED_DIRS


def collect_files(root_dir):
    py_files = []
    yaml_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if not is_allowed(os.path.relpath(dirpath, root_dir)):
            continue
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)
            if filename.endswith(".py"):
                py_files.append((rel_path, full_path))
            elif filename.endswith((".yaml", ".yml")):
                yaml_files.append((rel_path, full_path))
    return py_files, yaml_files


def write_section(file_handle, header, files):
    file_handle.write(header)
    current_folder = None
    for rel_path, full_path in sorted(files):
        folder = os.path.dirname(rel_path)
        if folder != current_folder:
            file_handle.write(f"\n# --- Folder: {folder or '.'} ---\n")
            current_folder = folder
        file_handle.write(f"\n# --- File: {rel_path } ---\n")
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_handle.write(f.read())
        except Exception as e:
            file_handle.write(f"# ERROR reading {rel_path }: {e }\n")


def create_combined_dump():
    py_files, yaml_files = collect_files(".")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        write_section(out, PYTHON_HEADER, py_files)
        write_section(out, YAML_HEADER, yaml_files)


if __name__ == "__main__":
    create_combined_dump()
    print(f"Script complete. Contents written to '{OUTPUT_FILE }'.")
