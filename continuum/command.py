"""
[pipeline]
TODO: describe module functionality.
"""

import subprocess
from typing import List, Optional, Union


def run_command(
    cmd: Union[str, List[str]],
    cwd: Optional[str] = None,
    capture_output: bool = True,
    check: bool = True,
    env: Optional[dict] = None,
    stream: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run a shell/system command. Returns a CompletedProcess object.
    - If stream is True, prints stdout/stderr live.
    - If capture_output, captures output in .stdout/.stderr.
    - Set shell=True to run a raw shell command string.
    """
    if stream:

        proc = subprocess.Popen(
            cmd,
            shell=shell,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
        lines = []
        try:
            for line in proc.stdout:
                print(line, end="")
                lines.append(line)
        finally:
            proc.stdout.close()
            proc.wait()
        return subprocess.CompletedProcess(
            args=cmd, returncode=proc.returncode, stdout="".join(lines), stderr=None
        )
    else:

        return subprocess.run(
            cmd,
            shell=shell,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            check=check,
            text=True,
        )


def run_and_get_stdout(cmd: Union[str, List[str]], **kwargs) -> str:
    """Run a command and return only stdout as string."""
    result = run_command(cmd, **kwargs)
    if hasattr(result, "stdout"):
        return result.stdout
    return ""
