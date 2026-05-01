"""LLM-based assertion inference strategy.

Builds a prompt (system prompt + optional examples + error + code + output instruction),
calls the LLM, and parses the JSON response into candidate assertion lists.
Supports multi-round inference via config.num_rounds.
"""

import logging
from pathlib import Path
from typing import Any

from src_new.config import AssertionInfererConfig, ExampleStrategy
from src_new.daisy.assertion_inference.base import register_assertion_strategy
from src_new.llm.extract_error_blocks import extract_error_blocks
from src_new.daisy.assertion_inference.llm_strategy import LLMAssertionStrategy
from src_new.llm.llm_configurations import LLM
from src_new.llm.parse_raw_response import parse_raw_response
from src_new.llm.retrieve_examples import (
    retrieve_examples,
    generate_example_model,
    retrieve_by_error_and_code,
    format_examples
)

logger = logging.getLogger(__name__)


@register_assertion_strategy("LLM_EXAMPLE")
class LLMExampleAssertionStrategy(LLMAssertionStrategy):
    """Generate assertion candidates by asking an LLM."""

    def __init__(
        self,
        llm: LLM,
        config: AssertionInfererConfig,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(llm, config,  cache_dir=cache_dir, **kwargs)
        self.llm = llm
        self.config = config
        self.llm.system_prompt = config.system_prompt


    def _add_error_message(self, prompt: str, error_output: str) -> str:
        """Append filtered error output to prompt if configured."""
        if self.config.add_error_message:
            prompt += "\nERROR:\n"
            error_text = error_output
            if self.config.filter_warnings:
                error_text = extract_error_blocks(error_text)
            prompt += error_text + "\n"
        return prompt

    def _build_prompt(
        self,
        method_text_with_placeholders: str,
        error_output: str,
        **kwargs: Any,
    ) -> str:
        method_text = method_text_with_placeholders
        base_prompt = super()._build_prompt(method_text, error_output)

        prog_name = kwargs.get("prog_name")
        group_name = kwargs.get("group_name")
        
        cfg = self.config
        if cfg.example_retrieval_type == ExampleStrategy.NONE or cfg.num_examples == 0:
            examples = []
        else :
            examples = retrieve_examples( cfg, method_text, error_output, prog_name, group_name)

        example_section = format_examples(examples)
        return base_prompt + example_section

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def _do_infer(
        self,
        method_text_with_placeholders: str,
        error_output: str,
        **kwargs: Any,
    ) -> list[list[str]]:
        all_candidates: list[list[str]] = []

        for _round in range(self.config.num_rounds):
            prompt = self._build_prompt(
                method_text_with_placeholders, error_output, **kwargs
            )
            self.llm.reset_chat_history()
            raw_response = self.llm.get_response(prompt)

            try:
                parsed = parse_raw_response(raw_response)
                # parsed is list[str | list[str]]; normalise to list[list[str]]
                round_candidates = self._normalise_parsed(parsed)
                all_candidates = self._merge_candidates(all_candidates, round_candidates)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Malformed JSON from LLM assertion response (round %d): %s",
                    _round,
                    exc,
                )
                # Design says: return empty list with warning logged OR raise
                # We log warning and continue; if all rounds fail, return what we have
                continue

        return all_candidates

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_parsed(parsed: list) -> list[list[str]]:
        """Normalise parse_raw_response output to list[list[str]].

        parse_raw_response returns list[Any]. The LLM should return a JSON
        array of arrays, but we handle both flat and nested forms.
        """
        if not parsed:
            return []

        # Already nested: [[...], [...]]
        if isinstance(parsed[0], list):
            return [
                [str(item) for item in inner]
                for inner in parsed
            ]

        # Flat list of strings — wrap in single inner list
        return [[str(item) for item in parsed]]

    @staticmethod
    def _merge_candidates(
        existing: list[list[str]], new: list[list[str]]
    ) -> list[list[str]]:
        """Merge candidates from multiple rounds.

        Each position index gets its candidates extended.
        """
        if not existing:
            return new
        if not new:
            return existing

        merged: list[list[str]] = []
        max_len = max(len(existing), len(new))
        for i in range(max_len):
            pos_candidates: list[str] = []
            if i < len(existing):
                pos_candidates.extend(existing[i])
            if i < len(new):
                pos_candidates.extend(new[i])
            merged.append(pos_candidates)
        return merged
