"""HYBRID position inference strategy.

Composes LAUREL_BETTER and LLM inferers internally.
Merge: LAUREL_BETTER positions first, then unique LLM positions after.
"""

from pathlib import Path
from typing import Any

from src.daisy.position_inference.base import PositionInferer, register_position_strategy


@register_position_strategy("HYBRID")
class HybridPositionStrategy(PositionInferer):
    """HYBRID — merges LAUREL_BETTER positions with LLM positions."""

    def __init__(
        self,
        laurel_better_inferer: PositionInferer,
        llm_inferer: PositionInferer,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(name="HYBRID", cache_dir=cache_dir, **kwargs)
        self.laurel_better_inferer = laurel_better_inferer
        self.llm_inferer = llm_inferer

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        laurel_positions = self.laurel_better_inferer._do_infer(method_text, error_output, **kwargs)
        llm_positions = self.llm_inferer._do_infer(method_text, error_output, **kwargs)
        return laurel_positions + [p for p in llm_positions if p not in laurel_positions]
