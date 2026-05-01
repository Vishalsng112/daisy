"""LAUREL_BETTER position inference strategy.

Thin subclass of LAURELPositionStrategy that uses the improved
placeholder_finder_better binary by setting use_laurel_better=True.
"""

from pathlib import Path
from typing import Any

from src.config import PositionInfererConfig
from src.daisy.position_inference.base import register_position_strategy
from src.daisy.position_inference.laurel_strategy import LAURELPositionStrategy


@register_position_strategy("LAUREL_BETTER")
class LAURELBetterPositionStrategy(LAURELPositionStrategy):
    """LAUREL_BETTER — uses the improved placeholder_finder binary."""

    def __init__(
        self,
        config: PositionInfererConfig,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            config=config,
            cache_dir=cache_dir,
            use_laurel_better=True,
            **kwargs,
        )
        self.name = "LAUREL_BETTER"
