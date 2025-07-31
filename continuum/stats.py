"""
Simple stats and progress tracking for Cliff Continuum.
"""

def file_stats(py_files):
    return {
        "total": len(py_files),
        "by_folder": {}
    }
