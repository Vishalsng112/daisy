"""Unit tests for Phase 1 foundation modules.

Tests:
- Config dataclasses instantiate with expected fields
- external_cmd runs trivial command → (Status.OK, "hello\n", "")
- parallel_executor processes identity function over list
- Data structures (FileInfo, MethodInfo) construct from test fixtures
- MODEL_REGISTRY accessible from llm.llm_configurations
- create_llm callable with debug stubs

Requirements: 7.1, 7.2, 7.3, 10.2, 14.1, 15.1
"""

import sys
import tempfile
from pathlib import Path

# Ensure src importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.config import (
    PositionInfererConfig,
    AssertionInfererConfig,
    VerificationConfig,
    LocStrategy,
    ExampleStrategy,
    VerificationType,
    ASSERTION_PLACEHOLDER,
)
from src.utils.external_cmd import run_external_cmd, Status
from src.utils.parallel_executor import run_parallel_or_seq
from src.utils.assertion_method_classes import FileInfo, MethodInfo, AssertionInfo
from src.llm.llm_configurations import MODEL_REGISTRY, ModelInfo, ProviderInfo, LLM
from src.llm.llm_create import create_llm


# ---- Config dataclasses (Req 7.1, 7.2, 7.3) ----

class TestConfigDataclasses:
    def test_position_inferer_config_defaults(self):
        cfg = PositionInfererConfig()
        assert isinstance(cfg.localization_base_prompt, str)
        assert cfg.example_retrieval_type == ExampleStrategy.NONE
        assert cfg.num_examples == 0
        assert cfg.example_weight == 0.5
        assert cfg.placeholder_text == ASSERTION_PLACEHOLDER

    def test_assertion_inferer_config_defaults(self):
        cfg = AssertionInfererConfig()
        assert isinstance(cfg.base_prompt, str)
        assert isinstance(cfg.system_prompt, str)
        assert cfg.num_assertions_to_test == 10
        assert cfg.num_rounds == 1
        assert cfg.example_retrieval_type == ExampleStrategy.NONE
        assert cfg.num_examples == 0
        assert cfg.add_error_message is True
        assert cfg.remove_empty_lines is True
        assert cfg.filter_warnings is True

    def test_verification_config_defaults(self):
        cfg = VerificationConfig()
        assert cfg.verification_type == VerificationType.PARALLEL_COMBO
        assert isinstance(cfg.dafny_exec, Path)
        assert isinstance(cfg.temp_dir, Path)
        assert cfg.skip_verification is False
        assert cfg.parallel is True
        assert cfg.verifier_time_limit == 60
        assert cfg.verifier_max_memory == 24
        assert cfg.placeholder_text == ASSERTION_PLACEHOLDER

    def test_position_inferer_config_custom(self):
        cfg = PositionInfererConfig(
            localization_base_prompt="custom",
            example_retrieval_type=ExampleStrategy.TFIDF,
            num_examples=5,
            example_weight=0.8,
            placeholder_text="/*PLACEHOLDER*/",
        )
        assert cfg.localization_base_prompt == "custom"
        assert cfg.example_retrieval_type == ExampleStrategy.TFIDF
        assert cfg.num_examples == 5

    def test_enums_have_expected_members(self):
        assert LocStrategy.LLM.value == "LLM"
        assert LocStrategy.HYBRID.value == "HYBRID"
        assert ExampleStrategy.DYNAMIC.value == "DYNAMIC"
        assert VerificationType.PARALLEL_COMBO.value == "PARALLEL_COMBO"


# ---- external_cmd (Req 11.3) ----

class TestExternalCmd:
    def test_echo_hello(self):
        status, stdout, stderr = run_external_cmd(["echo", "hello"], timeout=10)
        assert status == Status.OK
        assert stdout == "hello\n"
        assert stderr == ""

    def test_false_returns_error(self):
        status, stdout, stderr = run_external_cmd(["false"], timeout=10)
        assert status == Status.ERROR_EXIT_CODE


# ---- parallel_executor (Req 11.1) ----

class TestParallelExecutor:
    def test_identity_sequential(self):
        items = [1, 2, 3, 4, 5]
        results = run_parallel_or_seq(items, lambda x: x, desc="", parallel=False)
        assert sorted(results) == items

    def test_identity_parallel(self):
        items = list(range(10))
        results = run_parallel_or_seq(items, lambda x: x, desc="", parallel=True)
        assert sorted(results) == items

    def test_transform_function(self):
        items = [1, 2, 3]
        results = run_parallel_or_seq(items, lambda x: x * 2, desc="", parallel=False)
        assert sorted(results) == [2, 4, 6]

    def test_empty_list(self):
        results = run_parallel_or_seq([], lambda x: x, desc="", parallel=False)
        assert results == []


# ---- Data structures (Req 15.1) ----

class TestDataStructures:
    def test_fileinfo_from_fixture(self, tmp_path):
        """FileInfo loads a .dfy file and exposes text/bytes."""
        dfy = tmp_path / "test.dfy"
        dfy.write_text("method Foo() { }\n", encoding="utf-8")
        fi = FileInfo(dfy)
        assert fi.file_path == dfy
        assert "method Foo()" in fi.file_text
        assert isinstance(fi.file_bytes, bytes)
        assert fi.methods == []

    def test_methodinfo_from_fixture(self, tmp_path):
        """MethodInfo reads segment from file."""
        content = "// header\nmethod Bar() {\n  assert true;\n}\n"
        dfy = tmp_path / "bar.dfy"
        dfy.write_text(content, encoding="utf-8")
        fi = FileInfo(dfy)
        # Method starts at byte offset of "method"
        start = content.index("method")
        end = len(content.encode("utf-8")) - 2  # before final newline
        mi = MethodInfo(start, end, "Bar", fi)
        assert mi.method_name == "Bar"
        assert "method Bar()" in mi.segment_str
        assert mi.file is fi

    def test_assertioninfo_from_fixture(self, tmp_path):
        """AssertionInfo reads assertion segment."""
        content = "method Baz() {\n  assert x > 0;\n}\n"
        dfy = tmp_path / "baz.dfy"
        dfy.write_text(content, encoding="utf-8")
        fi = FileInfo(dfy)
        start_m = content.index("method")
        end_m = len(content.encode("utf-8")) - 2
        mi = MethodInfo(start_m, end_m, "Baz", fi)
        # assertion segment
        start_a = content.index("assert")
        end_a = content.index(";", start_a)
        ai = AssertionInfo(start_a, end_a, "assert", mi)
        assert ai.type == "assert"
        assert "assert x > 0" in ai.segment_str
        assert ai.method is mi


# ---- LLM module (Req 10.2, 14.1) ----

class TestLLMModule:
    def test_model_registry_accessible(self):
        assert isinstance(MODEL_REGISTRY, dict)
        assert len(MODEL_REGISTRY) > 0

    def test_debug_stubs_in_registry(self):
        assert "cost_stub_almost_real" in MODEL_REGISTRY
        assert "cost_stub_response_dafnybench" in MODEL_REGISTRY
        assert "without_api" in MODEL_REGISTRY

    def test_model_info_fields(self):
        info = MODEL_REGISTRY["cost_stub_almost_real"]
        assert isinstance(info, ModelInfo)
        assert info.provider.name == "debug"
        assert isinstance(info.max_context, int)
        assert isinstance(info.cost_1M_in, float)

    def test_create_llm_debug_stub_almost_real(self):
        llm = create_llm("test", "cost_stub_almost_real")
        assert isinstance(llm, LLM)
        # Should respond (debug stub echoes prompt-derived content)
        resp = llm.get_response("JSON array of line numbers ONLY test")
        assert isinstance(resp, str)

    def test_create_llm_debug_stub_dafnybench(self):
        llm = create_llm("test", "cost_stub_response_dafnybench")
        assert isinstance(llm, LLM)

    def test_create_llm_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            create_llm("test", "nonexistent_model_xyz")
