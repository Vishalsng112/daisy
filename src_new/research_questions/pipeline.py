"""RQ1: Best overall — evaluate different localization strategies.

Tests LLM, LAUREL, LAUREL_BETTER, HYBRID, ORACLE, and LLM_EXAMPLE
localization strategies with assertion inference and verification.

Three-phase pattern per (model, strategy) combo:
  1. Localization pass
  2. Assertion inference pass
  3. Verification pass

All results must be pre-cached; raises CacheMissError on miss.
"""

from __future__ import annotations

import os
from pathlib import Path

from src_new.config import (
    ASSERTION_PLACEHOLDER,
    DAFNY_ASSERTION_DATASET,
    DAFNY_EXEC,
    LLM_RESULTS_DIR,
    TEMP_FOLDER,
    AssertionInfererConfig,
    ExampleStrategy,
    LocStrategy,
    PositionInfererConfig,
    VerificationConfig,
)
from src_new.daisy.assertion_inference import LLMAssertionStrategy
from src_new.daisy.assertion_inference.base import ASSERTION_REGISTRY
from src_new.daisy.position_inference import (
    HybridPositionStrategy,
    LAURELBetterPositionStrategy,
    LAURELPositionStrategy,
    LLMExamplePositionStrategy,
    LLMPositionStrategy,
    OraclePositionStrategy,
)
from src_new.daisy.verification import ParallelComboVerification
from src_new.llm.llm_configurations import LLM
from src_new.llm.llm_create import create_llm
from src_new.research_questions import CacheMissError
from src_new.utils.assertion_method_classes import (
    assertionGroup,
    get_assertion_group_string_id,
    get_file_from_assertion_group,
    get_method_from_assertion_group,
)
from src_new.utils.dataset_class import Dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_example_config(
    strategy_name: str,
    example_type: ExampleStrategy,
    num_examples: int,
    label: str,
) -> None:
    """Ensure example config is consistent with the strategy.

    Raises ValueError on misconfiguration:
    - Strategies that use examples (LLM_EXAMPLE, HYBRID) require
      example_type != NONE and num_examples > 0.
    - Other strategies must not have examples configured.
    """
    uses_examples = strategy_name in ("LLM_EXAMPLE", "HYBRID")
    has_examples = example_type != ExampleStrategy.NONE and num_examples > 0

    if uses_examples and not has_examples:
        raise ValueError(
            f"{label}: {strategy_name} requires examples "
            f"(got s-examples={example_type.value}, n-examples={num_examples})"
        )
    if not uses_examples and (example_type != ExampleStrategy.NONE or num_examples > 0):
        raise ValueError(
            f"{label}: strategy {strategy_name} does not use examples "
            f"(got s-examples={example_type.value}, n-examples={num_examples})"
        )


def _build_model_dir_name(
    llm_name: str,
    loc: LocStrategy,
    inf: str = "LLM",
    example_type: ExampleStrategy = ExampleStrategy.NONE,
    example_type_pos: ExampleStrategy = ExampleStrategy.NONE,
    num_examples: int = 0,
    num_examples_pos: int = 0,
    example_weight: float = 0.5,
    example_weight_pos: float = 0.5,
) -> str:
    """Build a directory name that maps 1-to-1 to CLI flags.

    Format:
        {model}__loc_{LOC}_inf_{INF}[_sExPos_{S}_nExPos_{N}[_aExPos_{W}]][_sExInf_{S}_nExInf_{N}[_aExInf_{W}]]

    Position-example fields only appear when loc is LLM_EXAMPLE.
    Inference-example fields only appear when inf is LLM_EXAMPLE.
    """
    parts = [f"{llm_name}__loc_{loc.value}_inf_{inf}"]
    if example_type_pos != ExampleStrategy.NONE:
        parts.append(f"sExPos_{example_type_pos.value}")
        parts.append(f"nExPos_{num_examples_pos}")
        if example_type_pos == ExampleStrategy.DYNAMIC:
            parts.append(f"aExPos_{example_weight_pos}")
    if example_type != ExampleStrategy.NONE:
        parts.append(f"sExInf_{example_type.value}")
        parts.append(f"nExInf_{num_examples}")
        if example_type == ExampleStrategy.DYNAMIC:
            parts.append(f"aExInf_{example_weight}")
    return "_".join(parts)


def _group_cache_key(group: assertionGroup) -> str:
    """Build the cache sub-path for an assertion group: ``{prog_folder}/{group_id}``."""
    file = get_file_from_assertion_group(group)
    prog_folder = os.path.basename(file.file_path.parent.name)
    group_id = get_assertion_group_string_id(group)
    return f"{prog_folder}/{group_id}"


def _check_cache_completeness(
    groups: list[assertionGroup],
    pos_inferer,
    assert_inferer,
    phase: str,
) -> None:
    """Raise CacheMissError if any group lacks cached results."""
    if phase == "localization":
        missing = [
            _group_cache_key(g)
            for g in groups
            if not pos_inferer.check_cache(_group_cache_key(g))
        ]
    elif phase == "assertion":
        missing = [
            _group_cache_key(g)
            for g in groups
            if not assert_inferer.check_cache(_group_cache_key(g))
        ]
    else:
        return

    if missing:
        preview = missing[:10]
        raise CacheMissError(
            f"Missing {phase} cache for {len(missing)} groups: {preview}"
            + ("..." if len(missing) > 10 else ""),
            missing_entries=missing,
        )


def _prepare_method(group: assertionGroup, remove_empty_lines: bool = True):
    """Prepare method text with placeholders and full file text."""
    file = get_file_from_assertion_group(group)
    method = get_method_from_assertion_group(group)
    method_with_placeholders = method.get_method_with_assertion_group_changed(
        group, remove_empty_lines, ASSERTION_PLACEHOLDER,
    )
    _, full_file_text = file.substitute_method_with_text(method, method_with_placeholders)
    return method, method_with_placeholders, full_file_text


# ---------------------------------------------------------------------------
# Three-phase execution
# ---------------------------------------------------------------------------

def _run_localization_pass(
    groups: list[assertionGroup],
    pos_inferer,
) -> None:
    """Phase 1: localization — reads from cache."""
    for group in groups:
        key = _group_cache_key(group)
        method = get_method_from_assertion_group(group)
        pos_inferer.infer_positions(method.segment_str, "", cache_key=key)


def _run_assertion_pass(
    groups: list[assertionGroup],
    assert_inferer,
) -> None:
    """Phase 2: assertion inference — reads from cache."""
    for group in groups:
        key = _group_cache_key(group)
        _, method_with_placeholders, _ = _prepare_method(group)
        assert_inferer.infer_assertions(method_with_placeholders, "", cache_key=key)


def _run_verification_pass(
    groups: list[assertionGroup],
    pos_inferer,
    assert_inferer,
    verifier: ParallelComboVerification,
) -> list:
    """Phase 3: verification — combines cached localization + assertions."""
    results = []
    for group in groups:
        key = _group_cache_key(group)
        _, method_with_placeholders, full_file_text = _prepare_method(group)
        candidates = assert_inferer.infer_assertions(
            method_with_placeholders, "", cache_key=key,
        )
        result = verifier.verify_assertions(
            full_file_text, method_with_placeholders, candidates,
        )
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Per-strategy runner
# ---------------------------------------------------------------------------

def run_strategy(
    llm: LLM,
    loc_strategy: LocStrategy,
    groups: list[assertionGroup],
    results_dir: Path,
    dataset_path: Path,
    assertion_strategy: str = "LLM",
    example_type: ExampleStrategy = ExampleStrategy.NONE,
    example_type_pos: ExampleStrategy = ExampleStrategy.NONE,
    num_examples: int = 0,
    num_examples_pos: int = 0,
    example_weight: float = 0.5,
    example_weight_pos: float = 0.5,
) -> list:
    """Run three-phase evaluation for one (model, strategy) combo."""
    # Validate example config consistency
    _validate_example_config(
        loc_strategy.value, example_type_pos, num_examples_pos, "position",
    )
    _validate_example_config(
        assertion_strategy, example_type, num_examples, "inference",
    )

    model_dir_name = _build_model_dir_name(
        llm.get_name(), loc_strategy, assertion_strategy,
        example_type, example_type_pos,
        num_examples, num_examples_pos, example_weight, example_weight_pos,
    )
    model_dir = results_dir / model_dir_name
    os.makedirs(model_dir, exist_ok=True)

    pos_config = PositionInfererConfig(
        example_retrieval_type=example_type_pos,
        num_examples=num_examples_pos,
        example_weight=example_weight_pos,
    )
    assert_config = AssertionInfererConfig(
        example_retrieval_type=example_type,
        num_examples=num_examples,
        example_weight=example_weight,
    )
    verif_config = VerificationConfig()

    # Create inferers with cache_dir
    pos_inferer = _create_pos_inferer(
        llm, loc_strategy, pos_config, model_dir, dataset_path,
    )
    assert_inferer = _create_assert_inferer(
        assertion_strategy, llm, assert_config, model_dir,
    )
    verifier = ParallelComboVerification(config=verif_config)

    # Check cache completeness
    _check_cache_completeness(groups, pos_inferer, assert_inferer, "localization")
    _check_cache_completeness(groups, pos_inferer, assert_inferer, "assertion")

    # Three-phase execution
    print(f"\n  Localization pass ({loc_strategy.value})...")
    _run_localization_pass(groups, pos_inferer)

    print(f"  Assertion inference pass...")
    _run_assertion_pass(groups, assert_inferer)

    print(f"  Verification pass...")
    results = _run_verification_pass(groups, pos_inferer, assert_inferer, verifier)

    verified_count = sum(1 for r in results if r.verified)
    print(f"  Done: {verified_count}/{len(results)} verified")
    return results


def _create_pos_inferer(
    llm: LLM,
    loc: LocStrategy,
    config: PositionInfererConfig,
    cache_dir: Path,
    dataset_path: Path,
):
    """Factory for position inferers with cache_dir set."""
    if loc == LocStrategy.LLM:
        return LLMPositionStrategy(llm=llm, config=config, cache_dir=cache_dir)
    if loc == LocStrategy.LLM_EXAMPLE:
        return LLMExamplePositionStrategy(llm=llm, config=config, cache_dir=cache_dir)
    if loc == LocStrategy.LAUREL:
        return LAURELPositionStrategy(config=config, cache_dir=cache_dir)
    if loc == LocStrategy.LAUREL_BETTER:
        return LAURELBetterPositionStrategy(config=config, cache_dir=cache_dir)
    if loc == LocStrategy.ORACLE:
        return OraclePositionStrategy(dataset_path=dataset_path, cache_dir=cache_dir)
    if loc == LocStrategy.HYBRID:
        laurel = LAURELBetterPositionStrategy(config=config, cache_dir=None)
        llm_inf = LLMPositionStrategy(llm=llm, config=config, cache_dir=None)
        return HybridPositionStrategy(
            laurel_better_inferer=laurel, llm_inferer=llm_inf, cache_dir=cache_dir,
        )
    raise ValueError(f"Unknown localization strategy: {loc}")


def _create_assert_inferer(
    strategy: str,
    llm: LLM,
    config: AssertionInfererConfig,
    cache_dir: Path,
):
    """Factory for assertion inferers from the registry."""
    cls = ASSERTION_REGISTRY.get(strategy)
    if cls is None:
        raise ValueError(f"Unknown assertion strategy: {strategy}")
    return cls(llm=llm, config=config, cache_dir=cache_dir)
