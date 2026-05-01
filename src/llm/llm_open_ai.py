from openai import OpenAI
import openai
import time
import os

from .llm_configurations import LLM, ModelInfo


# Enforcing max data rate of 500 per minute
class OpenAI_LLM(LLM):
    def __init__(self, name: str, model: ModelInfo, verbose: bool = False):
        super().__init__(name, model)
        self.model = model
        self.chat_history = []
        self.verbose = verbose

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            api_key = "NO_KEY"

        if api_key == "NO_KEY":
            self.openai_client = None
            print("NO OPEN AI API key provided running in mock mode")
            return
        else:
            print("API KEY provided")

        try:
            self.openai_client = OpenAI(api_key=api_key)
            models = self.openai_client.models.list()
            if verbose:
                print("Avaiable models")
                for modelgotten in models:
                    print(modelgotten)
            print("API key is valid!")
        except openai.APIError as e:
            print(f"OpenAI API returned an API Error: {e}")
            exit()

    def _get_response(self, prompt: str) -> str:
        # to not exceed the 500 messages per second
        time.sleep(0.12)
        self.chat_history.append({"role": "user", "content": prompt})
        self._trim_context()
        reply: str
        if not self.openai_client:
            reply = "Mock Reply"
        else:
            my_messages = [{"role": "developer", "content": self.system_prompt}] + self.chat_history
            response = self.openai_client.chat.completions.create(
                model=self.model.model_id,
                messages=my_messages,
                reasoning_effort="none",
            )
            try:
                reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens or 0
            except Exception:
                reasoning_tokens = 0
            self.reasoning_tokens_output += reasoning_tokens
            if response.choices[0].message.content is None:
                reply = "None"
            else:
                reply = response.choices[0].message.content
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply

    def _trim_context(self):
        """Ensures the chat history fits within max_context_size tokens."""
        estimated_bytes = sum(len(m["content"]) for m in self.chat_history)
        if estimated_bytes > self.model.max_context:
            first_message = self.chat_history[0]
            trimmed_messages = self.chat_history[1:]
            while estimated_bytes > self.model.max_context and len(trimmed_messages) > 1:
                trimmed_messages.pop(0)
                estimated_bytes = sum(len(m["content"]) for m in [first_message] + trimmed_messages)
            self.chat_history = [first_message] + trimmed_messages
