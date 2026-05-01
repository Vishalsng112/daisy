"""Position inference abstractions and strategies."""

from src.daisy.position_inference.base import (
    POSITION_REGISTRY,
    PositionInferer,
    register_position_strategy,
)

# Import all strategies so their @register decorators execute
from src.daisy.position_inference.llm_strategy import (
    LLMPositionStrategy,
    PositionInferenceError,
)
from src.daisy.position_inference.llm_example_strategy import (
    LLMExamplePositionStrategy,
)
from src.daisy.position_inference.laurel_strategy import (
    LAURELPositionStrategy,
)
from src.daisy.position_inference.laurel_better_strategy import (
    LAURELBetterPositionStrategy,
)
from src.daisy.position_inference.oracle_strategy import (
    OraclePositionStrategy,
)
from src.daisy.position_inference.hybrid_strategy import (
    HybridPositionStrategy,
)

__all__ = [
    "POSITION_REGISTRY",
    "PositionInferer",
    "register_position_strategy",
    "LLMPositionStrategy",
    "LLMExamplePositionStrategy",
    "LAURELPositionStrategy",
    "LAURELBetterPositionStrategy",
    "OraclePositionStrategy",
    "HybridPositionStrategy",
    "PositionInferenceError",
]
