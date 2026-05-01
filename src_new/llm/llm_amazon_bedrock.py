import json
import time
import os
import boto3

from .llm_configurations import LLM, ModelInfo


class AmazonBedrock_LLM(LLM):
    def __init__(
        self,
        name: str,
        model: ModelInfo,
        verbose: bool = False,
    ):
        super().__init__(name, model)
        self.model = model
        self.verbose = verbose
        self.chat_history = []
        self.system_prompt = ""

        api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not api_key:
            api_key = "NO_KEY"
            raise ValueError("NO AWS_BEARER_TOKEN_BEDROCK, set it")
        else:
            print("BEDROCK KEY PROVIDED")

        region = os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise ValueError("No AWS_DEFAULT_REGION, set it, exampe us-east-2 tends to work well")

        if api_key == "NO_KEY":
            print("NO BEDROCK API key provided — running in mock mode")
            self.client = None
            return

        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=region,
        )

    def _get_response(self, prompt: str) -> str:
        if self.client is None:
            return "Mock Reply"

        bedrock_messages = [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in self.chat_history
        ]

        prompt_message = {"role": "user", "content": [{"text": prompt}]}
        bedrock_messages.append(prompt_message)

        response = self.client.converse(
            modelId=self.model.model_id,
            messages=bedrock_messages,
            system=[{"text": self.system_prompt}],
        )

        reply = response['output']['message']['content'][0]['text']
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply
