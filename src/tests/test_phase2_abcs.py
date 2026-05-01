"""Unit tests for Phase 2 ABCs: PositionInferer, AssertionInferer, VerificationStrategy.

Requirements: 1.1, 3.1, 5.1, 6.1, 6.5
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.daisy.position_inference.base import PositionInferer
from src.daisy.assertion_inference.base import AssertionInferer
from src.daisy.verification.base import VerificationResult, VerificationStrategy
from src.config import VerificationConfig


# ---------------------------------------------------------------------------
# Concrete test subclasses
# ---------------------------------------------------------------------------

class StubPositionInferer(PositionInferer):
    """Minimal concrete subclass for testing."""

    def __init__(self, cache_dir: Path | None = None, return_val: list[int] | None = None):
        super().__init__(name="stub-position", cache_dir=cache_dir)
        self.return_val = return_val or [1, 2, 3]
        self.do_infer_called = False

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        self.do_infer_called = True
        return self.return_val


class StubAssertionInferer(AssertionInferer):
    """Minimal concrete subclass for testing."""

    def __init__(self, cache_dir: Path | None = None, return_val: list[list[str]] | None = None):
        super().__init__(name="stub-assertion", cache_dir=cache_dir)
        self.return_val = return_val or [["assert x;"]]
        self.do_infer_called = False

    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        self.do_infer_called = True
        return self.return_val


# ---------------------------------------------------------------------------
# 1. Direct instantiation of each ABC raises TypeError
# ---------------------------------------------------------------------------

class TestABCInstantiation:
    def test_position_inferer_cannot_instantiate(self):
        with pytest.raises(TypeError):
            PositionInferer(name="bad")  # type: ignore[abstract]

    def test_assertion_inferer_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AssertionInferer(name="bad")  # type: ignore[abstract]

    def test_verification_strategy_cannot_instantiate(self):
        cfg = VerificationConfig()
        with pytest.raises(TypeError):
            VerificationStrategy(config=cfg)  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. check_cache returns False when cache_dir is None
# ---------------------------------------------------------------------------

class TestCheckCacheNone:
    def test_position_check_cache_none(self):
        inf = StubPositionInferer(cache_dir=None)
        assert inf.check_cache("any_key") is False

    def test_assertion_check_cache_none(self):
        inf = StubAssertionInferer(cache_dir=None)
        assert inf.check_cache("any_key") is False


# ---------------------------------------------------------------------------
# 3. check_cache returns False when cache_dir set but no cache file
# ---------------------------------------------------------------------------

class TestCheckCacheMiss:
    def test_position_check_cache_miss(self, tmp_path: Path):
        inf = StubPositionInferer(cache_dir=tmp_path)
        assert inf.check_cache("nonexistent_key") is False

    def test_assertion_check_cache_miss(self, tmp_path: Path):
        inf = StubAssertionInferer(cache_dir=tmp_path)
        assert inf.check_cache("nonexistent_key") is False


# ---------------------------------------------------------------------------
# 4. check_cache returns True when cache file exists
# ---------------------------------------------------------------------------

class TestCheckCacheHit:
    def test_position_check_cache_hit(self, tmp_path: Path):
        inf = StubPositionInferer(cache_dir=tmp_path)
        cache_file = inf._cache_path("mykey")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps([1, 2]))
        assert inf.check_cache("mykey") is True

    def test_assertion_check_cache_hit(self, tmp_path: Path):
        inf = StubAssertionInferer(cache_dir=tmp_path)
        cache_file = inf._cache_path("mykey")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps([["assert a;"]]))
        assert inf.check_cache("mykey") is True


# ---------------------------------------------------------------------------
# 5. cache_dir=None: _do_infer called, no file I/O
# ---------------------------------------------------------------------------

class TestNoCacheDirSkipsIO:
    def test_position_no_cache_no_files(self, tmp_path: Path):
        """cache_dir=None → _do_infer called, no files created in tmp dir."""
        inf = StubPositionInferer(cache_dir=None, return_val=[5, 10])
        result = inf.infer_positions("method", "error")
        assert result == [5, 10]
        assert inf.do_infer_called is True
        # Verify no files were created anywhere in tmp_path
        assert list(tmp_path.rglob("*")) == []

    def test_assertion_no_cache_no_files(self, tmp_path: Path):
        """cache_dir=None → _do_infer called, no files created in tmp dir."""
        inf = StubAssertionInferer(cache_dir=None, return_val=[["assert y;"]])
        result = inf.infer_assertions("method", "error")
        assert result == [["assert y;"]]
        assert inf.do_infer_called is True
        assert list(tmp_path.rglob("*")) == []


# ---------------------------------------------------------------------------
# 6. VerificationResult dataclass instantiation with expected fields
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_fields_present(self):
        vr = VerificationResult(
            verified=True,
            total_tested=10,
            verified_count=1,
            corrected_method_text="method fixed",
            corrected_file_text="file fixed",
        )
        assert vr.verified is True
        assert vr.total_tested == 10
        assert vr.verified_count == 1
        assert vr.corrected_method_text == "method fixed"
        assert vr.corrected_file_text == "file fixed"

    def test_none_fields(self):
        vr = VerificationResult(
            verified=False,
            total_tested=5,
            verified_count=0,
            corrected_method_text=None,
            corrected_file_text=None,
        )
        assert vr.verified is False
        assert vr.corrected_method_text is None
        assert vr.corrected_file_text is None


# ---------------------------------------------------------------------------
# 7. VerificationStrategy ABC can't be instantiated directly
#    (covered in TestABCInstantiation above, but explicit standalone too)
# ---------------------------------------------------------------------------

def test_verification_strategy_is_abstract():
    """VerificationStrategy with abstract verify_assertions can't be instantiated."""
    with pytest.raises(TypeError):
        VerificationStrategy(config=VerificationConfig())  # type: ignore[abstract]
