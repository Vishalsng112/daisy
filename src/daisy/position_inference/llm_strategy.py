"""LLM-based position inference strategy.

Formats a prompt with numbered method lines + verifier error output,
calls the LLM, and parses the JSON response into line numbers.
"""

from pathlib import Path
from typing import Any

from src.config import PositionInfererConfig
from src.daisy.position_inference.base import PositionInferer, register_position_strategy
from src.llm.llm_configurations import LLM
from src.llm.parse_raw_response import parse_raw_response


class PositionInferenceError(Exception):
    """Raised when position inference fails (e.g. unparseable LLM response)."""

    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


@register_position_strategy("LLM")
class LLMPositionStrategy(PositionInferer):
    """Predict assertion positions by asking an LLM."""

    def __init__(
        self,
        llm: LLM,
        config: PositionInfererConfig,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(name="LLM", cache_dir=cache_dir, **kwargs)
        self.llm = llm
        self.config = config
        self.llm.system_prompt = config.system_prompt

    # ------------------------------------------------------------------
    # Prompt construction — mirrors src/llm/llm_pipeline.py get_localization_prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, method_text: str, error_output: str) -> str:
        numbered_lines = "\n".join(
            f"{line_id}: {line}"
            for line_id, line in enumerate(method_text.splitlines())
        )
        err_section = (
            f"\n=== TASK === \n Verifier error:\n {error_output}\n Program (numbered):\n"
        )
        return (
            self.config.localization_base_prompt
            + err_section
            + numbered_lines
            + "\n OUTPUT: JSON array of line numbers ONLY, e.g. [2,5] (NO OTHER TEXT OR EXPLANATION)"
        )

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        prompt = self._build_prompt(method_text, error_output)
        self.llm.reset_chat_history()
        raw_response = self.llm.get_response(prompt)

        try:
            parsed = parse_raw_response(raw_response)
            # parse_raw_response returns list[str]; convert to list[int]
            return [int(x) for x in parsed]
        except (ValueError, TypeError) as exc:
            raise PositionInferenceError(
                f"Failed to parse LLM position response: {exc}",
                raw_response=raw_response,
            ) from exc
