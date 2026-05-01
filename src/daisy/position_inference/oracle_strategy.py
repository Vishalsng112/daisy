"""ORACLE position inference strategy.

Loads ground-truth positions from the dataset's ``oracle_fix_position.txt``
file rather than computing them.
"""

import json
from pathlib import Path
from typing import Any

from src.daisy.position_inference.base import PositionInferer, register_position_strategy


@register_position_strategy("ORACLE")
class OraclePositionStrategy(PositionInferer):
    """Return ground-truth positions read from the dataset."""

    def __init__(
        self,
        dataset_path: Path,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(name="ORACLE", cache_dir=cache_dir, **kwargs)
        self.dataset_path = Path(dataset_path)

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        """Read ``oracle_fix_position.txt`` from the dataset folder.

        Keyword args:
            dataset_folder (str | Path): Path to the specific assertion-group
                folder containing ``oracle_fix_position.txt``.  Falls back to
                ``self.dataset_path`` when not provided.
        """
        folder = Path(kwargs.get("dataset_folder", self.dataset_path))
        oracle_file = folder / "oracle_fix_position.txt"

        if not oracle_file.exists():
            raise FileNotFoundError(
                f"Oracle position file not found: {oracle_file}"
            )

        raw = oracle_file.read_text(encoding="utf-8").strip()
        positions: list[int] = json.loads(raw)
        return positions
