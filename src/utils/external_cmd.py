"""External command execution with timeout, memory detection, and structured status.

Follows fl_eval/execution/external_cmd.py pattern.
Returns (Status, stdout, stderr) tuple for every invocation.

Status Codes:
    OK: Successful execution (return code 0)
    TIMEOUT: Exceeded timeout (subprocess or detected in stderr)
    MEMORY_ERROR: OOM detected in stderr
    SYSTEMD_LAUNCH_ERROR: Command failed to launch (e.g., binary not found)
    ERROR_EXIT_CODE: Non-zero return code
"""

import subprocess
from enum import Enum

DEFAULT_TIMEOUT = 120  # seconds


class Status(Enum):
    OK = 0
    TIMEOUT = 1
    MEMORY_ERROR = 2
    SYSTEMD_LAUNCH_ERROR = 3
    ERROR_EXIT_CODE = 4


def run_external_cmd(
    cmd: list[str], timeout: int = DEFAULT_TIMEOUT
) -> tuple[Status, str, str]:
    """Run an external command with timeout and structured status return.

    Args:
        cmd: Command and arguments as a list of strings.
        timeout: Max seconds to wait. 0 or negative means no timeout.

    Returns:
        (Status, stdout, stderr) tuple.
    """
    try:
        if timeout > 0:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
        else:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
    except subprocess.TimeoutExpired as e:
        return Status.TIMEOUT, "", f"\nCommand timed out: {e}"
    except Exception as e:
        return Status.SYSTEMD_LAUNCH_ERROR, "", f"\nCommand failed to launch: {e}"

    stdout = result.stdout
    stderr = result.stderr
    rc = result.returncode

    # Check stderr for timeout/memory indicators
    if len(stderr) > 0:
        stderr_lower = stderr.lower()
        if "timed out" in stderr_lower:
            return Status.TIMEOUT, stdout, stderr
        if (
            "memory" in stderr_lower
            or "oom" in stderr_lower
            or "out of memory" in stderr_lower
        ):
            return Status.MEMORY_ERROR, stdout, stderr

    if rc != 0:
        return Status.ERROR_EXIT_CODE, stdout, stderr

    return Status.OK, stdout, stderr
