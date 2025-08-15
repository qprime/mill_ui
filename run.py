# path: run.py
# type: entrypoint script
# tags: web, whisper, context, graph, image, cam, headers
# owner: cliff
# depends_on: web.cliff_server.app,services.whisper.whisper_server,continuum.code_context,continuum.project_graph,skills.image_pipeline.generate_image,skills.cam_generator.runner,continuum.regen_metadata_headers
# description: Orchestrates running various project entrypoints based on command-line input with detailed error reporting.

import sys
import os
import runpy
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

ENTRYPOINTS = {
    "web": "web.cliff_server.app",
    "whisper": "services.whisper.whisper_server",
    "context": "continuum.code_context",
    "graph": "continuum.project_graph",
    "generate_image": "skills.image_pipeline.generate_image",
    "generate_cam": "skills.cam_generator.runner",
    "cam_v2": "skills.cam_generator_v2.runner",
    "cam_v3": "skills.cam_generator_v3.run_cam",
    "cam_v4": "skills.cam_generator_v4.cli",
    "regen_headers": "continuum.regen_metadata_headers",
    "ast": "continuum.ast_context",
    "metadata": "continuum.metadata",
}


def usage():
    print("Usage: run.py [entrypoint] [args...]")
    print("Available entrypoints:")
    for k in ENTRYPOINTS:
        print(f"  {k}: {ENTRYPOINTS[k]}")
    sys.exit(1)


def _print_error_report(entry: str, module: str, exc: BaseException):
    etype, evalue, tb = sys.exc_info()

    # Last traceback frame is typically where it failed
    last = traceback.extract_tb(tb)[-1] if tb else None
    filename = last.filename if last else "<unknown file>"
    lineno = last.lineno if last else 0
    func = last.name if last else "<unknown>"

    # Try to show the offending line with a caret
    line_src = ""
    caret = ""
    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if 1 <= lineno <= len(lines):
            src_line = lines[lineno - 1].rstrip("\n")
            line_src = f"\n    {src_line}\n" + "    " + (" " * (len(src_line) - len(src_line.lstrip()))) + "^\n"
            caret = ""
    except Exception:
        pass

    print("\n" + "=" * 80)
    print(f"[ERROR] Unhandled exception in entrypoint '{entry}' (module {module})")
    print(f"Type: {etype.__name__ if etype else type(exc).__name__}")
    print(f"Message: {evalue if evalue is not None else exc}")
    if last:
        print(f"Location: {filename}:{lineno} in {func}{line_src}")
    print("-" * 80)
    print("Full traceback:")
    traceback.print_exc()
    print("=" * 80 + "\n")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ENTRYPOINTS:
        usage()

    entry = sys.argv[1]
    module = ENTRYPOINTS[entry]
    args = sys.argv[2:]

    # Make project importable
    os.chdir(PROJECT_ROOT)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)

    # Announce what we're running
    print(f"[RUN] {sys.executable} -m {module} {' '.join(args)} (cwd: {PROJECT_ROOT})")

    # Run the module in-process so we can catch and report the exact failing line
    original_argv = sys.argv[:]
    try:
        sys.argv = [module] + args  # many entrypoints parse sys.argv
        # run_name="__main__" makes the module behave like `python -m module`
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return 0
    except SystemExit as e:
        # Allow entrypoints that call sys.exit(code) to pass through
        code = e.code if isinstance(e.code, int) else 1
        return code
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] KeyboardInterrupt")
        return 130  # typical SIGINT exit code
    except BaseException as exc:
        _print_error_report(entry, module, exc)
        return 1
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    sys.exit(main())
