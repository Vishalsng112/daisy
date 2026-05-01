# Daisy

Infer helper assertions in Dafny code using LLM-powered assertion repair.

Daisy takes a Dafny file that fails verification, predicts where helper assertions are needed, generates candidates via an LLM, and verifies them against the Dafny verifier — returning a corrected method if a fix is found.

## Getting Started

### Clone (with submodules)

This repo uses Git submodules for external dependencies (`dafny_fork`, `DafnyBenchFork`, `dafny_laurel_repair`). Clone recursively:

```sh
git clone --recurse-submodules git@github.com:VeriFixer/daisy.git
```

If you already cloned without `--recurse-submodules`:
```sh
git submodule update --init --recursive
```

### Fetch LFS files

Datasets and cached results are stored via [Git LFS](https://git-lfs.com/). After cloning, pull them:

```sh
git lfs install
git lfs pull
```

### Docker (recommended)

A Docker image is available that bundles Dafny, LAUREL, Python deps, and the dataset — no manual setup needed. See **[README_DOCKER.md](README_DOCKER.md)** for build/run instructions.

---

## Full cli command to pretify
python -m src.cli /home/ricostynha/Desktop/daisy/dataset/extracted_test/dafny_assertion_dataset_test/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy --model without_api --localization LLM_EXAMPLE --assertion LLM_EXAMPLE --n-examples-pos 3 --n-examples-inf 3 --s-examples-pos RANDOM


## Quick Start

```sh
python -m src.cli myfile.dfy --model openrouter-free --localization LLM
```

No dataset needed. Just point it at a `.dfy` file.

Debug mode (no API key):
```sh
python -m src.cli myfile.dfy --model cost_stub_almost_real
```

## Walkthrough: Fixing a Lemma

Consider this inductive lemma that fails verification — the inductive step is missing a hint:

```dafny
lemma {:induction false} Divby2(n: nat)
ensures (n*(n-1))%2 == 0
{
    if n == 0 {
        assert (1*(1-1))%2 == 0;
    } else {
        Divby2(n - 1);
         // ← missing: assert (n-1)*(n-2) == n*n - 3*n + 2;
    }
}
```

Run Daisy on it:
```sh
python -m src.cli example.dfy --model openrouter-free --localization LLM
```

Daisy will:
1. Verify the file → finds it fails
2. Localize → predicts line 7 needs an assertion
3. Infer → generates 10 candidate assertions
4. Verify → tests combinations against Dafny
5. Output the corrected method (or "no fix found")

You can try this on a real dataset example:
```sh
python -m src.cli \
  dataset/extracted/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy \
  --model openrouter-free --localization LLM
```

## CLI Options

| Argument | Default | Description |
|---|---|---|
| `file` (positional) | *(required)* | Path to `.dfy` file |
| `--localization` | `LLM` | Position strategy: `LLM`, `LLM_EXAMPLE`, `LAUREL`, `LAUREL_BETTER`, `HYBRID`, `NONE` |
| `--model` | `openrouter-free` | Model from registry (see table below) |
| `--num-assertions` | `10` | Candidates per position |
| `--rounds` | `1` | Independent inference rounds |
| `--no-color` | `False` | Disable colored output |

### Localization Strategies

| Strategy | Description |
|---|---|
| `LLM` | Ask the LLM to predict assertion positions from numbered code + error |
| `LLM_EXAMPLE` | Same as LLM but prepends similar examples from the dataset |
| `LAUREL` | Static analysis via external C# `placeholder_finder` binary |
| `LAUREL_BETTER` | Improved LAUREL heuristics |
| `HYBRID` | LAUREL_BETTER positions first, then unique LLM positions |
| `NONE` | Skip localization (file must already contain placeholder strings) |

### More Examples

```sh
# HYBRID localization (combines static + LLM)
python -m src.cli myfile.dfy --model gpt-4.1 --localization HYBRID

# More candidates, multiple rounds
python -m src.cli myfile.dfy --model claude-haiku-4.5 --num-assertions 15 --rounds 2

# LAUREL-only (no LLM for localization, still uses LLM for assertion generation)
python -m src.cli myfile.dfy --model openrouter-free --localization LAUREL_BETTER
```

### Dataset Examples (Sorted by Difficulty)

The extracted dataset contains programs with helper assertions removed. Each entry has the broken program, verifier errors, and ground truth.

```sh
# Extract dataset (if not done)
tar xzf dataset/dafny_assertion_dataset.tar.gz -C dataset/extracted/
```

**1. Lemma hint** — 1 missing assert, algebraic expansion:
```sh
python -m src.cli \
  dataset/extracted/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy
```

**2. Sequence sum** — 2 missing asserts, sequence slicing hints:
```sh
python -m src.cli \
  dataset/extracted/dafny_assertion_dataset/dafny-duck_tmp_tmplawbgxjo_p1_dfy/method_start_162_as_start_406_end_443_as_start_475_end_499/program_without_assertion_group.dfy \
  --localization HYBRID
```

**3. Set counting** — 1 missing assert, set comprehension decomposition:
```sh
python -m src.cli \
  dataset/extracted/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy \
  --localization LLM --num-assertions 15
```

Compare with ground truth:
```sh
cat dataset/extracted/dafny_assertion_dataset/Clover_count_lessthan_dfy/original_program.dfy
```

## Available Models

| Name | Provider | Model ID |
|---|---|---|
| `claude-opus-4.5` | bedrock | `us.anthropic.claude-opus-4-5-20251101-v1:0` |
| `claude-sonnet-4.5` | bedrock | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `claude-haiku-4.5` | bedrock | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `deepseek-r1` | bedrock | `us.deepseek.r1-v1:0` |
| `qwen3-coder-480b` | bedrock | `qwen.qwen3-coder-480b-a35b-v1:0` |
| `qwen3-coder-30b` | bedrock | `qwen.qwen3-coder-30b-a3b-v1:0` |
| `llama-3.3-70b` | bedrock | `meta.llama3-3-70b-instruct-v1:0` |
| `gpt-5.2` | openai | `gpt-5.2` |
| `gpt-5-mini` | openai | `gpt-5-mini` |
| `gpt-4.1` | openai | `gpt-4.1-2025-04-14` |
| `openrouter-free` | openrouter | `openrouter/free` |
| `qwen3-coder-free` | openrouter | `qwen/qwen3-coder:free` |
| `cost_stub_almost_real` | debug | *(no API key needed)* |
| `cost_stub_response_dafnybench` | debug | *(no API key needed)* |
| `without_api` | debug | *(no API key needed)* |

### API Keys

| Provider | Environment Variable |
|---|---|
| OpenRouter | `OPENROUTER_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Bedrock | `AWS_BEARER_TOKEN_BEDROCK` + `AWS_DEFAULT_REGION` |

Missing keys → provider falls back to mock mode.

---

## Replicating Research Questions

The research scripts run batch evaluation over the full dataset using cached results. They require pre-computed inference results (included in the compressed archives).

### Setup

```sh
# Extract dataset + results (~10GB)
./extract_saved_results_tars.sh
```

### Running RQ Scripts

```sh
# RQ1: Best overall — evaluates localization strategies across models
python -m src.research_questions.main_rq1

# RQ2: Fault localization — localization strategies without example retrieval
python -m src.research_questions.main_rq2

# RQ3: Example retrieval — assertion inference with different example strategies
python -m src.research_questions.main_rq3
```

All scripts follow the same three-phase pattern:
1. **Localization pass** — reads cached position predictions
2. **Assertion inference pass** — reads cached assertion candidates
3. **Verification pass** — tests combinations against Dafny

Scripts error out with `CacheMissError` listing exact missing entries if any results are not cached. There is no RQ4 script — RQ4 uses RQ1 data with different analysis.

### Data Analysis (Jupyter Notebooks)

The figures and tables from the paper are generated by notebooks in `src/`:

| Notebook | Paper Section |
|---|---|
| `src/data_analysys_dataset_overview.ipynb` | Figures 2, 3 |
| `src/data_analysys_pre_tests.ipynb` | Table 2 |
| `src/data_analysys_cost_statistics.ipynb` | Table 3 |
| `src/data_analysys_rq1_best_overall.ipynb` | RQ1 |
| `src/data_analysys_rq2_loc_strategy.ipynb` | RQ2 |
| `src/data_analysys_rq3_example_retrieval.ipynb` | RQ3 |
| `src/data_analysys_rq4_different_llms.ipynb` | RQ4 |

Launch via Docker (see [README_DOCKER.md](README_DOCKER.md) section 7) or locally:
```sh
jupyter lab
```

### Recomputing Inference Results

To rerun experiments (not just read cached results):

```sh
# Cost estimation first (uses debug stubs)
python -m src.research_questions.main_rq1
python -m src.research_questions.main_rq2
python -m src.research_questions.main_rq3
```

Each script has a cost-estimation section (before `exit()`) and an execution section (after). Comment the `exit()` to run actual experiments. Full replication takes ~6 compute days on a 6-core machine.

### (Optional) Recreating the Dataset from Scratch

```sh
python -m src.datasets.full_dataset_creator  # ~48 hours, 6 cores, 24GB RAM
```

This runs 5 steps:
1. Extract assertions from DafnyBench via `asserttree`
2. Generate w/o-1, w/o-2, w/o-all assertion-removal test cases
3. Compute original verifier errors + oracle positions
4. Compute syntactically valid assertion positions
5. Compute all valid fix positions

---

## Installation

> Skip if using Docker — see [README_DOCKER.md](README_DOCKER.md).

### 1. Extract Data

```sh
./extract_saved_results_tars.sh
```

### 2. Build Dafny

Requires .NET SDK 8.0 and z3 4.15.4:
```sh
cd external/dafny_fork && make
```

### 3. Build LAUREL (Optional — only for LAUREL/LAUREL_BETTER/HYBRID localization)

```sh
cd external/dafny_laurel_repair/laurel/placeholder_finder
dotnet build placeholder_finder.csproj

cd ../placeholder_finder_better
dotnet build placeholder_finder_laurel_better.csproj
```

### 4. Python Dependencies

```sh
pip install -r src/requirements.txt
```

### 5. Verify

```sh
python -m pytest src/tests/ -q
```

---

## Docker

See [README_DOCKER.md](README_DOCKER.md) for build/run instructions.

Quick single-file run via Docker:
```sh
docker run --rm -it -w /app dafny_research:latest \
  python -m src.cli \
    dataset/extracted/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy \
    --model cost_stub_almost_real
```

### Docker Memory Note

The Dafny verifier can enter unbounded memory loops. Inside Docker, memory is limited via z3 solver options (`--solver-option:O:memory_max_size`). Outside Docker, `systemd-run` can also be used. Default limit: 24GB.

---

## Project Structure

```
src/                              # Main codebase
├── cli.py                        # Single-file CLI entry point
├── config.py                     # Shared config, enums, dataclasses
├── daisy/
│   ├── position_inference/       # Position prediction strategies
│   │   ├── base.py               #   PositionInferer ABC
│   │   ├── llm_strategy.py       #   LLM-based
│   │   ├── llm_example_strategy.py  # LLM + retrieved examples
│   │   ├── laurel_strategy.py    #   LAUREL static analysis
│   │   ├── laurel_better_strategy.py # LAUREL+ improved
│   │   ├── oracle_strategy.py    #   Ground-truth from dataset
│   │   └── hybrid_strategy.py    #   LAUREL_BETTER + LLM merge
│   ├── assertion_inference/      # Assertion generation strategies
│   │   ├── base.py               #   AssertionInferer ABC
│   │   ├── llm_strategy.py       #   LLM-based
│   │   └── oracle_strategy.py    #   Ground-truth from dataset
│   └── verification/             # Verification strategies
│       ├── base.py               #   VerificationStrategy ABC
│       └── parallel_combo.py     #   Parallel combo testing
├── llm/                          # LLM providers (OpenAI, Bedrock, OpenRouter)
├── utils/                        # External cmd, parallel executor, data structures
├── research_questions/           # RQ1-3 batch evaluation scripts
├── analysis/                     # Results reader, position evaluation
├── datasets/                     # Dataset creation scripts
│   ├── full_dataset_creator.py   #   Full pipeline entry point
│   ├── dafny_get_all_assertions.py  # Step 1: extract from DafnyBench
│   ├── dafny_dataset_generator.py   # Step 2: generate w/o-1,2,all
│   └── assertion_test_generator.py  # Assertion removal + XML helpers
└── tests/                        # Unit + property tests (198 tests)

dataset/                          # Dafny assertion dataset
external/                         # Dafny fork, LAUREL binaries
results/                          # Cached experiment results
```

---

## Extending with New Models

Add to `MODEL_REGISTRY` in `src/llm/llm_configurations.py`:

```python
"my-model": ModelInfo(
    provider=ProviderInfo(name="openai", module="llm_open_ai"),
    model_id="my-model-id",
    max_context=128_000,
    cost_1M_in=2.50,
    cost_1M_out=10.00,
),
```

Then use it:
```sh
python -m src.cli myfile.dfy --model my-model
```

---

## Dataset Structure

### `dataset/extracted/dafny_assertion_dataset/`

```
{program_folder}/
├── original_program.dfy              # Ground truth (with correct assertions)
└── {assertion_group_id}/
    ├── info.xml                      # Method + assertion byte positions
    ├── program_without_assertion_group.dfy  # Broken program (assertions removed)
    ├── method_without_assertion_group.dfy   # Just the method (assertions removed)
    ├── verifier_output.txt           # Pre-computed Dafny errors
    ├── oracle_assertions.json        # Ground-truth assertion strings
    └── oracle_fix_position.txt       # Ground-truth line positions
```


---

## Extending the Pipeline

The three core pipeline stages — localization, assertion inference, and verification — each use an abstract base class with transparent caching. Adding a new strategy means subclassing the ABC, implementing one method, and wiring it into the CLI.

### Adding a Localization Strategy

Localization predicts *where* in a method to insert assertions. Each strategy implements `_do_infer` returning 0-based line numbers.

**1. Create the strategy** in `src/daisy/position_inference/`:

```python
# src/daisy/position_inference/my_strategy.py
from pathlib import Path
from typing import Any
from src.daisy.position_inference.base import PositionInferer

class MyPositionStrategy(PositionInferer):
    def __init__(self, cache_dir: Path | None = None, **kwargs: Any):
        super().__init__(name="MY_STRATEGY", cache_dir=cache_dir, **kwargs)

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        """Return 0-based line numbers after which to insert assertions."""
        # Your logic here. Receives:
        #   method_text  — the method source code
        #   error_output — Dafny verifier error output
        #   kwargs       — optional extras (method_name, program_text, etc.)
        return [3, 7]  # example: insert after lines 3 and 7
```

Caching is automatic — if `cache_dir` is set, results are saved to `{cache_dir}/{cache_key}/localization/localization_raw_response.txt` and reused on subsequent runs.

**2. Register in the CLI** — add to `create_position_inferer` in `src/cli.py`:

```python
from src.daisy.position_inference.my_strategy import MyPositionStrategy

# Inside create_position_inferer():
factories = {
    ...
    "MY_STRATEGY": lambda: MyPositionStrategy(cache_dir=cache_dir),
}
```

**3. Add to CLI choices** — append `"MY_STRATEGY"` to `LOCALIZATION_CHOICES` in `cli.py`.

**4. Export** — add to `src/daisy/position_inference/__init__.py`:

```python
from src.daisy.position_inference.my_strategy import MyPositionStrategy
```

### Adding an Assertion Inference Strategy

Assertion inference generates *what* assertions to try at each placeholder position. Each strategy implements `_do_infer` returning a list of candidate lists (one per position).

**1. Create the strategy** in `src/daisy/assertion_inference/`:

```python
# src/daisy/assertion_inference/my_strategy.py
from pathlib import Path
from typing import Any
from src.daisy.assertion_inference.base import AssertionInferer

class MyAssertionStrategy(AssertionInferer):
    def __init__(self, cache_dir: Path | None = None, **kwargs: Any):
        super().__init__(name="MY_ASSERT", cache_dir=cache_dir, **kwargs)

    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        """Return candidate assertions per placeholder position.

        Example: 2 positions, 3 candidates each:
        [
            ["assert x > 0;", "assert x >= 0;", "assert x != 0;"],
            ["assert |s| > 0;", "assert s != [];", "assert |s| >= 1;"],
        ]
        """
        return [["assert true;"]]  # placeholder
```

Cache path: `{cache_dir}/{cache_key}/assertions_list/assertions_parsed.json`.

**2. Wire into the CLI** — in `src/cli.py` `main()`, replace or add alongside the existing `LLMAssertionStrategy`:

```python
from src.daisy.assertion_inference.my_strategy import MyAssertionStrategy
assert_inferer = MyAssertionStrategy(cache_dir=run_dir)
candidates = assert_inferer.infer_assertions(localized_text, error_output)
```

To make it selectable via CLI flag, add an `--assertion-strategy` argument to `build_parser()` and dispatch in `main()`.

### Adding a Verification Strategy

Verification tests assertion combinations against the Dafny verifier. Each strategy implements `verify_assertions` returning a `VerificationResult`.

**1. Create the strategy** in `src/daisy/verification/`:

```python
# src/daisy/verification/my_verifier.py
from typing import Any
from src.config import VerificationConfig
from src.daisy.verification.base import VerificationResult, VerificationStrategy

class MyVerificationStrategy(VerificationStrategy):
    def __init__(self, config: VerificationConfig, **kwargs: Any):
        super().__init__(config, **kwargs)

    def verify_assertions(
        self,
        full_file_text: str,
        method_text_with_placeholders: str,
        candidates: list[list[str]],
    ) -> VerificationResult:
        """Test assertion candidates. Return first verified combo.

        Args:
            full_file_text: Complete .dfy file with placeholders still in place.
            method_text_with_placeholders: Method text with placeholder strings.
            candidates: One inner list per placeholder position.

        Steps:
            1. Generate combos from candidates (e.g. cartesian product, zip, etc.)
            2. For each combo: replace placeholders → run Dafny verify
            3. Return VerificationResult with first success or all-failed summary.
        """
        return VerificationResult(
            verified=False,
            total_tested=0,
            verified_count=0,
            corrected_method_text=None,
            corrected_file_text=None,
        )
```

The existing `ParallelComboVerification` uses `zip_with_empty_indexed` to generate combos (zipped rows first, then individual leftovers). You could implement a different grouping strategy — e.g. cartesian product, beam search, or priority-based ordering.

**2. Wire into the CLI** — in `src/cli.py` `main()`:

```python
from src.daisy.verification.my_verifier import MyVerificationStrategy
verifier = MyVerificationStrategy(config=VerificationConfig())
result = verifier.verify_assertions(full_file, localized_text, candidates)
```

### Key Interfaces Summary

| Stage | Base Class | Method to Implement | Input | Output |
|---|---|---|---|---|
| Localization | `PositionInferer` | `_do_infer(method_text, error_output)` | Method code + errors | `list[int]` (line numbers) |
| Assertion | `AssertionInferer` | `_do_infer(method_text_with_placeholders, error_output)` | Method with placeholders + errors | `list[list[str]]` (candidates per position) |
| Verification | `VerificationStrategy` | `verify_assertions(full_file, method_with_placeholders, candidates)` | Full file + candidates | `VerificationResult` |

All strategies receive `**kwargs` for extensibility. Localization strategies commonly use `method_name` and `program_text` as extra kwargs (needed by LAUREL/HYBRID).
