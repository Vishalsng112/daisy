"""ORACLE assertion inference strategy.

Loads ground-truth assertions from the dataset's ``oracle_assertions.json``
file rather than computing them.
"""

import json
from pathlib import Path
from typing import Any

from src.daisy.assertion_inference.base import AssertionInferer, register_assertion_strategy


@register_assertion_strategy("ORACLE")
class OracleAssertionStrategy(AssertionInferer):
    """Return ground-truth assertions read from the dataset."""

    def __init__(
        self,
        dataset_path: Path,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(name="ORACLE", cache_dir=cache_dir, **kwargs)
        self.dataset_path = Path(dataset_path)

    def _do_infer(
        self,
        method_text_with_placeholders: str,
        error_output: str,
        **kwargs: Any,
    ) -> list[list[str]]:
        """Read ``oracle_assertions.json`` from the dataset folder.

        Keyword args:
            dataset_folder (str | Path): Path to the specific assertion-group
                folder containing ``oracle_assertions.json``.  Falls back to
                ``self.dataset_path`` when not provided.

        Returns:
            list[list[str]]: Each inner list holds the oracle assertion(s) for
            one placeholder position.  The on-disk format is a flat
            ``list[str]``; each element is wrapped into its own inner list so
            the return type matches the ``AssertionInferer`` contract.
        """
        folder = Path(kwargs.get("dataset_folder", self.dataset_path))
        oracle_file = folder / "oracle_assertions.json"

        if not oracle_file.exists():
            raise FileNotFoundError(
                f"Oracle assertions file not found: {oracle_file}"
            )

        raw: list[str] = json.loads(oracle_file.read_text(encoding="utf-8"))
        # Wrap each assertion string into its own inner list — one per position.
        return [[a] for a in raw]
