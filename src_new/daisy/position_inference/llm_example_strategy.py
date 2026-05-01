"""LLM_EXAMPLE position inference strategy.

Extends the LLM strategy by prepending retrieved examples to the prompt
before calling the LLM. Uses retrieve_examples.retrieve_by_error_and_code()
to find similar error/code pairs from the dataset.
"""

from pathlib import Path
from typing import Any

from src_new.config import ExampleStrategy, PositionInfererConfig
from src_new.daisy.position_inference.base import register_position_strategy
from src_new.daisy.position_inference.llm_strategy import LLMPositionStrategy
from src_new.llm.extract_error_blocks import extract_error_blocks
from src_new.llm.llm_configurations import LLM
from src_new.llm.retrieve_examples import (
    generate_example_model,
    retrieve_by_error_and_code,
    retrieve_examples,
    format_examples
)


@register_position_strategy("LLM_EXAMPLE")
class LLMExamplePositionStrategy(LLMPositionStrategy):
    """Predict assertion positions using an LLM with retrieved examples prepended."""

    def __init__(
        self,
        llm: LLM,
        config: PositionInfererConfig,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(llm=llm, config=config, cache_dir=cache_dir, **kwargs)
        self.name = "LLM_EXAMPLE"

    @staticmethod
    def _format_examples(examples: list[dict]) -> str:
        return format_examples(examples)

    # ------------------------------------------------------------------
    # Override prompt construction to prepend examples
    # ------------------------------------------------------------------

    def _build_prompt(self, method_text: str, error_output: str, **kwargs: Any) -> str:
        base_prompt = super()._build_prompt(method_text, error_output)

        prog_name = kwargs.get("prog_name")
        group_name = kwargs.get("group_name")

        cfg = self.config
        if cfg.example_retrieval_type == ExampleStrategy.NONE or cfg.num_examples == 0:
            examples = []
        else :
            examples = retrieve_examples( cfg, method_text, error_output, prog_name, group_name)

        example_section = self._format_examples(examples)

        return base_prompt + example_section

    # ------------------------------------------------------------------
    # Override _do_infer to pass kwargs through to _build_prompt
    # ------------------------------------------------------------------

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        prompt = self._build_prompt(method_text, error_output, **kwargs)
        self.llm.reset_chat_history()
        raw_response = self.llm.get_response(prompt)

        from src_new.llm.parse_raw_response import parse_raw_response
        from src_new.daisy.position_inference.llm_strategy import PositionInferenceError

        try:
            parsed = parse_raw_response(raw_response)
            return [int(x) for x in parsed]
        except (ValueError, TypeError) as exc:
            raise PositionInferenceError(
                f"Failed to parse LLM position response: {exc}",
                raw_response=raw_response,
            ) from exc
