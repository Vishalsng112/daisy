import json
from dataclasses import dataclass
from typing import Any
from src.llm_model_registry import ModelInfo, ProviderInfo


@dataclass(frozen=True)
class LLMCostSnapshot:
    model_name: str
    model_id: str
    total_prompts: int
    total_chars_prompted: int
    total_chars_response: int
    total_tokens_input: float
    total_tokens_output: float
    total_tokens_output_reason: float
    cost_input_usd: float
    cost_output_usd: float
    cost_output_reason_usd: float
    total_cost_usd: float

    def to_metadata_dict(self) -> dict[str, str | int | float]:
        return {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "total_prompts": self.total_prompts,
            "total_chars_prompted": self.total_chars_prompted,
            "total_chars_response": self.total_chars_response,
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_tokens_output_reason": self.total_tokens_output_reason,
            "cost_input_usd": self.cost_input_usd,
            "cost_output_usd": self.cost_output_usd,
            "cost_output_reason_usd": self.cost_output_reason_usd,
            "total_cost_usd": self.total_cost_usd,
        }

class LLM:
    def __init__(self, name: str, model: ModelInfo):
        self.name = name
        self.model = model

        self.system_prompt = ""

        # Handled directly by this parent class
        self.total_chars_prompted: int = 0
        self.total_chars_response: int = 0
        self.prompt_number: int = 0

        # Variable to be handled by the implementations
        self.reasoning_tokens_output: int = 0

        self.chat_history: list[Any] = []

    def __str__(self):
        return f"LLM({self.name})"
    
    def get_name(self):
        return self.name

    def set_system_prompt(self, message: str):
        self.system_prompt = message

    def reset_chat_history(self):
        self.chat_history = []

    def get_chat_history(self):
        return self.chat_history

    def _get_response(self, prompt: str) -> str:
        raise NotImplementedError("Subclasses must implement the _generate_response method for API interaction.")

    def get_response(self, prompt: str) -> str:
        """Public method that handles logging and calls the subclass's implementation."""
        prompt_len = len(prompt)
        self.total_chars_prompted += prompt_len
        self.prompt_number += 1

        response = self._get_response(prompt)

        response_len = len(response)
        self.total_chars_response += response_len

        return response

    def get_my_cost_statisitcs(self):
        return self.get_cost_statistics(self.model)

    # Backward-compatible alias with corrected spelling.
    def get_my_cost_statistics(self):
        return self.get_my_cost_statisitcs()

    def get_cost_snapshot(self, model: ModelInfo | None = None) -> LLMCostSnapshot:
        mi = self.model if model is None else model

        # Rule of thumb for rough token accounting in plain-text prompts/responses.
        how_many_chars_per_token = 3
        num_tokens_input = self.total_chars_prompted / how_many_chars_per_token
        num_tokens_output = self.total_chars_response / how_many_chars_per_token

        cost_input = (num_tokens_input / 1_000_000) * mi.cost_1M_in
        cost_output = (num_tokens_output / 1_000_000) * mi.cost_1M_out
        cost_reasoning = (self.reasoning_tokens_output / 1_000_000) * mi.cost_1M_out
        total_cost = cost_input + cost_output + cost_reasoning

        return LLMCostSnapshot(
            model_name=self.name,
            model_id=mi.model_id,
            total_prompts=self.prompt_number,
            total_chars_prompted=self.total_chars_prompted,
            total_chars_response=self.total_chars_response,
            total_tokens_input=num_tokens_input,
            total_tokens_output=num_tokens_output,
            total_tokens_output_reason=float(self.reasoning_tokens_output),
            cost_input_usd=cost_input,
            cost_output_usd=cost_output,
            cost_output_reason_usd=cost_reasoning,
            total_cost_usd=total_cost,
        )

    def get_cost_statistics(self, model: ModelInfo):
        snapshot = self.get_cost_snapshot(model)

        print(f"Expected Prices Model name: {snapshot.model_name} Model id: {snapshot.model_id}")
        print(f"{'Statistic':<40}{'Value':<20}")
        print("=" * 40)
        print(f"{'Total Prompts ':<40}{snapshot.total_prompts:<20}")
        print(f"{'Total Chars Prompted ':<40}{snapshot.total_chars_prompted:<20}")
        print(f"{'Total Chars Response ':<40}{snapshot.total_chars_response:<20}")
        print(f"{'Total Tokens Input ':<40}{snapshot.total_tokens_input:<20.2f}")
        print(f"{'Total Tokens Output ':<40}{snapshot.total_tokens_output:<20.2f}")
        print(f"{'Total Tokens Output Reason':<40}{snapshot.total_tokens_output_reason:<20.2f}")
        print(f"{'Cost Input ($) ':<40}{snapshot.cost_input_usd:<20.6f}")
        print(f"{'Cost Output ($) ':<40}{snapshot.cost_output_usd:<20.6f}")
        print(f"{'Cost Output Reason($) ':<40}{snapshot.cost_output_reason_usd:<20.6f}")
        print(f"{'Total Cost ($) ':<40}{snapshot.total_cost_usd:<20.6f}")
        print("=" * 40)
        return snapshot

    def reset_all_measurement(self):
        self.total_chars_prompted = 0
        self.total_chars_response = 0
        self.prompt_number = 0


# Debug stubs

class LLM_EMPTY_RESPONSE_STUB(LLM):
    def _get_response(self, prompt: str) -> str:
        return ""


class LLM_COST_STUB_RESPONSE_IS_LIKE_DAFNYBENCH(LLM):
    def _get_response(self, prompt: str):
        self.chat_history.append(prompt)
        needle = " === TASK === "
        start_task_pos = prompt.find(needle)
        start_task_pos += len(needle)

        task_text = prompt[start_task_pos:]
        needle = "CODE:"

        avg_added_assertion = "assert 123452==123452 && 4 == 4;" * 2

        start_code = task_text.find(needle)
        start_code += len(needle)
        end_code = task_text[start_code:].find("OUTPUT:")
        response = task_text[start_code:start_code + end_code]
        response += avg_added_assertion
        self.chat_history.append(response)
        return response


class LLM_COST_STUB_RESPONSE_IS_PROMPT(LLM):
    def _get_response(self, prompt: str):
        self.chat_history.append(prompt)
        if "JSON array of line numbers ONLY" in prompt:
            response = json.dumps([10, 11])
        else:
            response = json.dumps([[f"assert 123452==123452 && {i} == {i};" for i in range(10)] * 2])
        self.chat_history.append(response)
        return response


class LLM_YIELD_RESULT_WITHOUT_API(LLM):
    def _get_response(self, prompt: str):
        self.chat_history.append(prompt)
        print("The prompt is Prompt\n")
        print(f"System Prompt: {self.system_prompt}\n")
        print(f"Main Prompt: {prompt}\n")

        response = input("Enter your response (write #END# to end):\n")

        lines = [response]
        while True:
            line = input()
            if line == "#END#":
                break
            lines.append(line)

        response = "\n".join(lines)
        self.chat_history.append(response)
        return response