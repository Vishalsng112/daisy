# Feature: daisy-codebase-rewrite, Property 12: External command utility returns structured output
"""Property test: run_external_cmd always returns (Status, str, str) with valid Status member.

**Validates: Requirements 11.3**

Strategies:
- echo with random strings → Status.OK
- 'true' → Status.OK
- 'false' → Status.ERROR_EXIT_CODE
- sleep with small values + tiny timeout → Status.TIMEOUT
- Nonexistent binary → Status.SYSTEMD_LAUNCH_ERROR
"""

import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.utils.external_cmd import run_external_cmd, Status

VALID_STATUSES = set(Status)


# --- Helpers ---

def assert_structured_output(result: tuple) -> None:
    """Assert result is (Status, str, str) with valid Status."""
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 3, f"Expected 3-tuple, got length {len(result)}"
    status, stdout, stderr = result
    assert isinstance(status, Status), f"Expected Status enum, got {type(status)}"
    assert status in VALID_STATUSES, f"Unknown status: {status}"
    assert isinstance(stdout, str), f"stdout not str: {type(stdout)}"
    assert isinstance(stderr, str), f"stderr not str: {type(stderr)}"


# --- Property tests ---

@settings(max_examples=100)
@given(text=st.text(alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
                     min_size=0, max_size=50))
def test_echo_returns_ok_structured(text: str) -> None:
    """echo with any safe string → (Status.OK, str, str)."""
    result = run_external_cmd(["echo", text], timeout=10)
    assert_structured_output(result)
    assert result[0] == Status.OK


@settings(max_examples=100)
@given(data=st.data())
def test_true_false_structured(data: st.DataObject) -> None:
    """'true' → OK, 'false' → ERROR_EXIT_CODE. Always structured."""
    cmd_name = data.draw(st.sampled_from(["true", "false"]))
    result = run_external_cmd([cmd_name], timeout=10)
    assert_structured_output(result)
    if cmd_name == "true":
        assert result[0] == Status.OK
    else:
        assert result[0] == Status.ERROR_EXIT_CODE


@settings(max_examples=30, deadline=15000)
@given(sleep_ms=st.integers(min_value=2, max_value=5))
def test_timeout_returns_structured(sleep_ms: int) -> None:
    """sleep longer than timeout → TIMEOUT status, still structured."""
    result = run_external_cmd(["sleep", str(sleep_ms)], timeout=1)
    assert_structured_output(result)
    assert result[0] == Status.TIMEOUT


@settings(max_examples=100)
@given(name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=10, max_size=30)
       .map(lambda s: f"__nonexistent_bin_{s}__"))
def test_nonexistent_cmd_structured(name: str) -> None:
    """Nonexistent binary → SYSTEMD_LAUNCH_ERROR, still structured."""
    result = run_external_cmd([name], timeout=5)
    assert_structured_output(result)
    assert result[0] == Status.SYSTEMD_LAUNCH_ERROR


@settings(max_examples=100)
@given(code=st.integers(min_value=1, max_value=125))
def test_exit_code_returns_error_structured(code: int) -> None:
    """bash -c 'exit N' for N>0 → ERROR_EXIT_CODE, structured."""
    result = run_external_cmd(["bash", "-c", f"exit {code}"], timeout=10)
    assert_structured_output(result)
    assert result[0] == Status.ERROR_EXIT_CODE
