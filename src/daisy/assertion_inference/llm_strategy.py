"""LLM-based assertion inference strategy.

Builds a prompt (system prompt + optional examples + error + code + output instruction),
calls the LLM, and parses the JSON response into candidate assertion lists.
Supports multi-round inference via config.num_rounds.
"""

import logging
from pathlib import Path
from typing import Any

from src.config import AssertionInfererConfig, ExampleStrategy
from src.daisy.assertion_inference.base import AssertionInferer, register_assertion_strategy
from src.llm.extract_error_blocks import extract_error_blocks
from src.llm.llm_configurations import LLM
from src.llm.parse_raw_response import parse_raw_response

logger = logging.getLogger(__name__)


class AssertionInferenceError(Exception):
    """Raised when assertion inference fails (e.g. unparseable LLM response)."""

    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


@register_assertion_strategy("LLM")
class LLMAssertionStrategy(AssertionInferer):
    """Generate assertion candidates by asking an LLM."""

    def __init__(
        self,
        llm: LLM,
        config: AssertionInfererConfig,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        super().__init__(name="LLM", cache_dir=cache_dir, **kwargs)
        self.llm = llm
        self.config = config
        self.llm.system_prompt = config.system_prompt

    # ------------------------------------------------------------------
    # Prompt construction — mirrors src/llm/llm_pipeline.py get_base_prompt
    # ------------------------------------------------------------------

    def _add_error_message(self, prompt: str, error_output: str) -> str:
        """Append filtered error output to prompt if configured."""
        if self.config.add_error_message:
            prompt += "\nERROR:\n"
            error_text = error_output
            if self.config.filter_warnings:
                error_text = extract_error_blocks(error_text)
            prompt += error_text + "\n"
        return prompt

    def _add_examples(
        self,
        prompt: str,
        method_text_with_placeholders: str,
        error_output: str,
        **kwargs: Any,
    ) -> str:
        """Append retrieved examples to prompt if configured."""
        if (
            self.config.example_retrieval_type == ExampleStrategy.NONE
            or self.config.num_examples == 0
        ):
            return prompt

        import ast
        from src.llm.retrieve_examples import (
            generate_example_model,
            retrieve_by_error_and_code,
        )

        error_txt_filter = extract_error_blocks(error_output)

        prog_name = kwargs.get("prog_name", "")
        group_name = kwargs.get("group_name", "")

        entries, model, device, tfidf_vectorizer, tfidf_matrix = generate_example_model()
        results = retrieve_by_error_and_code(
            error_txt_filter,
            method_text_with_placeholders,
            entries,
            top_k=-1,
            method=self.config.example_retrieval_type,
            α=self.config.example_weight,
            prog_original=prog_name,
            group_original=group_name,
            model=model,
            device=device,
            diferent_methods=1,
            tfidf_vectorizer=tfidf_vectorizer,
            tfidf_matrix=tfidf_matrix,
        )

        if self.config.example_retrieval_type == ExampleStrategy.RANDOM:
            import random
            random.shuffle(results)

        example_prompt = "Consider these examples: \n"
        for rank, r in enumerate(results, 1):
            if rank > self.config.num_examples:
                break
            filtered_error = extract_error_blocks(r["error_message"])
            example_prompt += "=== EXAMPLE ===\n"
            example_prompt += f"Error:\n{filtered_error}\n"
            example_prompt += f"CODE:\n{r['code_snippet']}\n"
            assertion_list = ast.literal_eval(r["assertions"])
            example_prompt += f"OUTPUT (as this is oracle only one option is shown the one that fixes the problem): \n {[[x] for x in assertion_list]}\n"
            example_prompt += "=== END ===\n"

        return prompt + example_prompt

    def _build_prompt(
        self,
        method_text_with_placeholders: str,
        error_output: str,
        **kwargs: Any,
    ) -> str:
        """Build full prompt: system prompt + examples + error + code + output instruction."""
        prompt = self.config.base_prompt
        prompt = self._add_examples(
            prompt, method_text_with_placeholders, error_output, **kwargs
        )
        prompt += "\n === TASK === \n"
        prompt = self._add_error_message(prompt, error_output)
        prompt += "\nCODE:\n" + method_text_with_placeholders
        prompt += (
            "\nOUTPUT:\n"
            "Enter your response as a JSON array of arrays "
            "(containing the assertions to fix the program) ONLY, "
            "no extra text. (NO OTHER TEXT OR EXPLANATION)"
        )
        return prompt

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
