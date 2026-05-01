"""LAUREL position inference strategy.

Calls the external C# placeholder_finder binary via run_external_cmd,
parses its output to find assertion placeholder tags, extracts 0-based
line numbers, and replaces tags with the configured placeholder text.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from src.config import PositionInfererConfig, PATH_TO_LAUREL
from src.daisy.position_inference.base import PositionInferer, register_position_strategy
from src.daisy.position_inference.llm_strategy import PositionInferenceError
from src.utils.external_cmd import Status, run_external_cmd

logger = logging.getLogger(__name__)

# Tag emitted by the C# placeholder_finder binary
LAUREL_ASSERTION_TAG = "<assertion> Insert assertion here </assertion>"

# Relative path from LAUREL dir to the built binary
_LAUREL_BINARY_REL = "placeholder_finder/bin/Debug/net6.0/placeholder_finder"


@register_position_strategy("LAUREL")
class LAURELPositionStrategy(PositionInferer):
    """Predict assertion positions using the LAUREL C# placeholder_finder."""

    def __init__(
        self,
        config: PositionInfererConfig,
        laurel_binary_path: Path | None = None,
        cache_dir: Path | None = None,
        use_laurel_better: bool = False,
        **kwargs: Any,
    ):
        super().__init__(name="LAUREL", cache_dir=cache_dir, **kwargs)
        self.config = config
        self.use_laurel_better = use_laurel_better

        if laurel_binary_path is not None:
            self.binary_path = laurel_binary_path
        elif use_laurel_better:
            self.binary_path = (
                PATH_TO_LAUREL
                / "placeholder_finder_better/bin/Debug/net6.0/placeholder_finder_laurel_better"
            )
        else:
            self.binary_path = PATH_TO_LAUREL / _LAUREL_BINARY_REL

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        """Write method to temp file, call placeholder_finder, parse output.

        Keyword args:
            method_name (str): Short method name (e.g. "BinarySearch").
                               Defaults to "UnknownMethod".
            program_text (str): Full .dfy program text. If provided, written
                                to the temp file instead of method_text alone.
        """
        method_name: str = kwargs.get("method_name", "UnknownMethod")
        program_text: str = kwargs.get("program_text", method_text)

        # Write program to a temp file — placeholder_finder needs a file path
        tmp = Path(tempfile.mktemp(suffix=".dfy"))
        try:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(program_text, encoding="utf-8")

            cmd = [
                str(self.binary_path),
                str(tmp),
                method_name,
                "False",  # multiple_locations
            ]

            status, stdout, stderr = run_external_cmd(cmd, timeout=120)

            if status != Status.OK:
                raise PositionInferenceError(
                    f"LAUREL binary failed (status={status.name}): {stderr}",
                )

            if not stdout.strip():
                raise PositionInferenceError(
                    "LAUREL binary produced no output.",
                )

            return self._parse_output(stdout)
        finally:
            tmp.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_output(output: str) -> list[int]:
        """Parse LAUREL output, extract 0-based line numbers of assertion tags.

        The binary returns the method text with ``<assertion> Insert assertion
        here </assertion>`` tags inserted at predicted positions. We find those
        lines, record their *original* 0-based index (accounting for the extra
        lines the tags add), and return the list.
        """
        positions: list[int] = []
        added_lines = 0
        for idx, line in enumerate(output.splitlines()):
            if LAUREL_ASSERTION_TAG in line:
                added_lines += 1
                # Original line index = current index minus tags seen so far
                positions.append(idx - added_lines)
        return positions
