from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderInfo:
    name: str

PROVIDER_BEDROCK = ProviderInfo(name="bedrock")
PROVIDER_OPENAI = ProviderInfo(name="openai")
PROVIDER_OPENROUTER = ProviderInfo(name="openrouter")
PROVIDER_DEBUG = ProviderInfo(name="debug")

@dataclass(frozen=True)
class ModelInfo:
    provider: ProviderInfo
    model_id: str          # provider-specific model id
    max_context: int
    cost_1M_in: float
    cost_1M_out: float

MODEL_REGISTRY: dict[str, ModelInfo] = {
    "claude-opus-4.5": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="us.anthropic.claude-opus-4-5-20251101-v1:0",
        max_context=200_000,
        cost_1M_in=5.00,
        cost_1M_out=25.00,
    ),
    "claude-sonnet-4.5": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_context=200_000,
        cost_1M_in=3.00,
        cost_1M_out=15.00,
    ),
    "claude-haiku-4.5": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        max_context=200_000,
        cost_1M_in=1.00,
        cost_1M_out=5.00,
    ),

    "deepseek-r1": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="us.deepseek.r1-v1:0",
        max_context=64_000,
        cost_1M_in=1.35,
        cost_1M_out=5.40,
    ),
    "qwen3-coder-480b": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="qwen.qwen3-coder-480b-a35b-v1:0",
        max_context=262_000,
        cost_1M_in=0.45,
        cost_1M_out=1.8,
    ),
    "qwen3-coder-30b": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="qwen.qwen3-coder-30b-a3b-v1:0",
        max_context=128_000,
        cost_1M_in=0.15,
        cost_1M_out=0.60,
    ),
    "llama-3.3-70b": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="meta.llama3-3-70b-instruct-v1:0",
        max_context=128_000,
        cost_1M_in=0.72,
        cost_1M_out=0.72,
    ),

    "gpt-5.2": ModelInfo(
        provider=PROVIDER_OPENAI,
        model_id="gpt-5.2",
        max_context=400_000,
        cost_1M_in=1.75,
        cost_1M_out=14.00,
    ),
    "gpt-5-mini": ModelInfo(
        provider=PROVIDER_OPENAI,
        model_id="gpt-5-mini",
        max_context=400_000,
        cost_1M_in=0.25,
        cost_1M_out=2.00,
    ),
    "gpt-4.1": ModelInfo(
        provider=PROVIDER_OPENAI,
        model_id="gpt-4.1-2025-04-14",
        max_context=128_000,
        cost_1M_in=2.00,
        cost_1M_out=8.00,
    ),

    "openrouter-free": ModelInfo(
        provider=PROVIDER_OPENROUTER,
        model_id="openrouter/free",
        max_context=131_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),
    "qwen3-coder-free": ModelInfo(
        provider=PROVIDER_OPENROUTER,
        model_id="qwen/qwen3-coder:free",
        max_context=256_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),

    "cost_stub_response_dafnybench": ModelInfo(
        provider=PROVIDER_DEBUG,
        model_id="cost_stub_response_dafnybench",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),
    "cost_stub_almost_real": ModelInfo(
        provider=PROVIDER_DEBUG,
        model_id="cost_stub_almost_real",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),
    "without_api": ModelInfo(
        provider=PROVIDER_DEBUG,
        model_id="without_api",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),
}