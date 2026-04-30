# Daisy

Infer helper annotations in Dafny code using LLM-powered assertion repair.

## Quick Start

```sh
PYTHONPATH=src python src/single_file_run.py myfile.dfy
```

This runs the full pipeline (extract methods → verify → localize → infer assertions → verify candidates) on a single `.dfy` file using the default free OpenRouter model.

## CLI Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `path_to_code` | positional | *(required)* | Path to the `.dfy` file to analyze |
| `--method` | string | `None` | Method name to analyze. If omitted, the first failing method is selected |
| `--error-file` | string | `None` | Pre-computed verifier error file. Skips initial verification when provided |
| `--localization` | choice | `LLM` | Localization strategy: `LLM`, `LLM_EXAMPLE`, `LAUREL`, `LAUREL_BETTER`, `HYBRID`, `NONE` |
| `--examples` | choice | `NONE` | Example retrieval strategy: `NONE`, `RANDOM`, `TFIDF`, `EMBEDDED`, `DYNAMIC` |
| `--model` | string | `openrouter-free` | Model name from `MODEL_REGISTRY` (see table below) |
| `--num-assertions` | int | `10` | Number of assertion candidates per position |
| `--rounds` | int | `1` | Number of independent inference rounds |
| `--no-color` | flag | `False` | Disable colored terminal output (useful when piping to files or agents) |

### Examples

```sh
# Use a specific model and localization strategy
PYTHONPATH=src python src/single_file_run.py myfile.dfy --model gpt-4.1 --localization HYBRID

# Analyze a specific method with pre-computed errors
PYTHONPATH=src python src/single_file_run.py myfile.dfy --method MyMethod --error-file errors.txt

# Run in mock mode (no API key needed)
PYTHONPATH=src python src/single_file_run.py myfile.dfy --model cost_stub_almost_real
```

## Example Files (Helper Assertion Repair)

This pipeline repairs **helper `assert` statements** — not loop invariants. The extracted dataset (`dataset/dafny_assertion_dataset.tar.gz`) contains programs with specific helper assertions removed, along with pre-computed verifier errors. Each dataset entry has:

- `program_without_assertion_group.dfy` — the broken program (assertions removed, invariants intact)
- `verifier_output.txt` — pre-computed Dafny errors (use with `--error-file` to skip verification)
- `original_program.dfy` — ground truth with correct assertions

Extract the dataset first (if not already done):
```sh
mkdir -p dataset/extracted
tar xzf dataset/dafny_assertion_dataset.tar.gz -C dataset/
```

Below are curated examples sorted by difficulty. All paths relative to project root.

### 1. Lemma hint — `SENG2011_exam_ex4` (9 lines, 1 assert)

Inductive lemma proving `n*(n-1) % 2 == 0`. Needs an algebraic expansion hint in the inductive step: `assert (n-1)*(n-2) == n*n - 3*n + 2`.

```sh
# Full pipeline (verify + localize + infer)
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy

# Skip verification using pre-computed errors
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy \
  --error-file dataset/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/verifier_output.txt
```

### 2. Sequence sum — `dafny-duck_p1` (16 lines, 2 asserts)

Array sum via recursive `Sum` function. Needs two sequence-slicing hints: `assert xs[..i+1] == xs[..i] + [xs[i]]` inside the loop and `assert xs[..] == xs[..i]` after it.

```sh
# LLM localization
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/dafny-duck_tmp_tmplawbgxjo_p1_dfy/method_start_162_as_start_406_end_443_as_start_475_end_499/program_without_assertion_group.dfy \
  --localization LLM

# HYBRID localization
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/dafny-duck_tmp_tmplawbgxjo_p1_dfy/method_start_162_as_start_406_end_443_as_start_475_end_499/program_without_assertion_group.dfy \
  --localization HYBRID

# With pre-computed errors
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/dafny-duck_tmp_tmplawbgxjo_p1_dfy/method_start_162_as_start_406_end_443_as_start_475_end_499/program_without_assertion_group.dfy \
  --error-file dataset/dafny_assertion_dataset/dafny-duck_tmp_tmplawbgxjo_p1_dfy/method_start_162_as_start_406_end_443_as_start_475_end_499/verifier_output.txt \
  --localization LLM
```

### 3. Real sqrt test — `DafnyProjects_sqrt` (17 lines, 1 assert)

Tests that `sqrt(4.0) == 2.0` using monotonic-square lemma. Needs `assert r == 2.0` after ruling out `r < 2.0`.

```sh
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/DafnyProjects_tmp_tmp2acw_s4s_sqrt_dfy/method_start_94_as_start_228_end_243/program_without_assertion_group.dfy \
  --localization LLM

PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/DafnyProjects_tmp_tmp2acw_s4s_sqrt_dfy/method_start_94_as_start_228_end_243/program_without_assertion_group.dfy \
  --localization LAUREL_BETTER
```

### 4. Set counting — `Clover_count_lessthan` (20 lines, 1 assert)

Counts elements below a threshold in a set. Needs a set-comprehension decomposition hint: `assert (set i | i in grow' && i < threshold) == (set i | i in grow && i < threshold) + if i < threshold then {i} else {}`.

```sh
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy \
  --localization LLM --num-assertions 15

PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy \
  --localization HYBRID --num-assertions 15

# With pre-computed errors + LAUREL
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy \
  --error-file dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/verifier_output.txt \
  --localization LAUREL
```

### 5. Multiset slice — `Clover_only_once` (21 lines, 1 assert)

Checks if a key appears exactly once. Needs `assert a[..a.Length] == a[..]` after the loop to connect the invariant to the postcondition.

```sh
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/Clover_only_once_dfy/method_start_0_as_start_460_end_489/program_without_assertion_group.dfy \
  --localization LLM

PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/Clover_only_once_dfy/method_start_0_as_start_460_end_489/program_without_assertion_group.dfy \
  --localization LAUREL_BETTER
```

### 6. Divisibility lemma — `summer-school exercise01` (19 lines, 2 asserts)

Predicate `divides(a, b)` with test assertions `assert divides(2, 6)` and `assert divides(3, 9)`.

```sh
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise01_solution_dfy/method_start_153_as_start_257_end_277_as_start_324_end_344/program_without_assertion_group.dfy \
  --localization LLM

PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise01_solution_dfy/method_start_153_as_start_257_end_277_as_start_324_end_344/program_without_assertion_group.dfy \
  --localization HYBRID --rounds 2
```

### 7. Array content — `dafny-exercise maxArray` (22 lines, 1 assert)

Tests `maxArray` by asserting array contents after initialization: `assert arr[0] == -11 && arr[1] == 2 && arr[2] == 42 && arr[3] == -4`.

```sh
PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/dafny-exercise_tmp_tmpouftptir_maxArray_dfy/method_start_424_as_start_517_end_584/program_without_assertion_group.dfy \
  --localization LLM

PYTHONPATH=src python src/single_file_run.py \
  dataset/dafny_assertion_dataset/dafny-exercise_tmp_tmpouftptir_maxArray_dfy/method_start_424_as_start_517_end_584/program_without_assertion_group.dfy \
  --localization LAUREL --examples TFIDF
```

### Comparing with ground truth

Each dataset entry's parent folder contains the verified original:

```sh
# View ground truth (with correct assertions)
cat dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/original_program.dfy

# Diff to see exactly which assertions were removed
diff \
  dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/method_start_0_as_start_460_end_591/program_without_assertion_group.dfy \
  dataset/dafny_assertion_dataset/Clover_count_lessthan_dfy/original_program.dfy
```

### Docker one-liner

```sh
docker run --rm -it \
  -v "$(pwd)/src:/app/src:delegated" \
  -w /app \
  dafny_research:latest bash -c \
  'PYTHONPATH=src python src/single_file_run.py \
    dataset/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy \
    --localization LLM'
```

---

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
| `cost_stub_response_dafnybench` | debug | `cost_stub_response_dafnybench` |
| `cost_stub_almost_real` | debug | `cost_stub_almost_real` |
| `without_api` | debug | `without_api` |

Debug models require no API key and are useful for testing the pipeline setup.

## API Key Configuration

Each provider requires specific environment variables:

| Provider | Environment Variables |
|---|---|
| **OpenRouter** | `OPENROUTER_API_KEY` |
| **OpenAI** | `OPENAI_API_KEY` |
| **Bedrock** | `AWS_BEARER_TOKEN_BEDROCK` and `AWS_DEFAULT_REGION` |

If the required key is not set, the provider falls back to mock mode (returns stub responses).

## Example Output

```
═══ Dafny Assertion Repair ═══
File: example.dfy
Model: openrouter-free (openrouter/free)

── Verification ──
Status: NOT_VERIFIED
Errors:
  example.dfy(11,20): Error: invariant could not be proved...

Selected method: ExampleMethod

── Localization ──
Strategy: LLM
Predicted lines: [6, 8]

── Assertion Inference ──
Candidates (10 per position, 2 positions):
  Position 1: ["assert X;", "assert Y;", ...]
  Position 2: ["assert A;", "assert B;", ...]

── Verification ──
Tested 20 combinations, 1 verified ✓

── Corrected Method ──
method ExampleMethod(...) {
  ...
  assert count == |set i | i in grow && i < threshold|;
  ...
}
```

---

## Research / Paper Replication

### Replicating Paper Results Without Recomputing Dataset

You can use the jupyter notebooks to get all info used on the paper on data analysis.

The figures used in the paper are generated using three scripts, all of which output their results under the `images/` folder:

* `src/data_analysys_dataset_overview.ipynb` — Figures 2 and 3 of the paper
* `src/data_analysys_pre_tests.ipynb` — Table 2 (accuracy; cost was manually added with consumed tokens info)
* `src/data_analysys_cost_statistics.ipynb` — Table 3
* `src/data_analysys_rq1_best_overall.ipynb` — RQ1
* `src/data_analysys_rq2_loc_strategy.ipynb` — RQ2
* `src/data_analysys_rq1_best_overall.ipynb` — RQ3
* `src/data_analysys_rq4_different_llms.ipynb` — RQ4

To launch the notebooks via Docker follow section 7 of [README_DOCKER.md](README_DOCKER.md).
(If file-not-found errors occur, you forgot to extract experimental results first.)

### Replicating Paper Recomputing Inference Results

Explore the main scripts:

* `src/main_rq1_best_overall.py`
* `src/main_rq2_fault_localization.py`
* `src/main_rq3_example_retrieval.py`

These scripts demonstrate how to **estimate costs and run experiments** for replicating the paper results.
(Note: there is no `main_rq4` — RQ4 uses data from RQ1 with different analysis.)

#### Overview

The scripts are divided into two parts:

1. **Cost Estimation (before `exit()`)** — Uses a cost-stub LLM to simulate queries and collect cost statistics. A `llm_without_api` debug mode exists for interactive prompt inspection.

   You must comment both `evaluate_all` calls before `exit()` (especially `llm_without_api`) to run with actual models. You must also comment the `exit()` to proceed.

2. **Actual Experiment Execution (after `exit()`)** — Runs experiments performing localization inference, assertion inference, and verification (multicore).

### Replicating Everything Including Dataset Creation

Optional — you can use the precomputed dataset.

#### (Optional) Compute Full Dataset from Scratch

This took ~48 hours with 6 parallel cores, 24GB RAM capped:
```sh
cd src
python full_dataset_creator.py
```

Results are already present in:
- `dataset/dafny_assertion_all/` — assertions for every file
- `dataset/dafny_assertion_dataset/` — extracted helper assertions only

### Considerations for Full Reproducibility

When running `main_rq*`, results are dumped to `results/dafny_llm_results`. They must be manually copied to the folder matching the specific data analysis. Results from RQ4 correspond to some models run in RQ1 and must also be copied manually.

Full replication requires ~6 compute days on a 6-core machine.

---

## Installation

> Skip if using the Dockerfile — all dependencies are pre-installed there. See the Dockerfile for exact steps.

### Extract Experimental Results

All experiment results are compressed. Run at the project root (requires ~10GB):
```shell
./extract_saved_results_tars.sh
```

Compressed folders:
* `dataset/dafny_assertion_dataset.tar.gz`
* `dataset/dafny_assertion_dataset_test.tar.gz`
* `results/dafny_llm_results_pre_test__testing_different_models.tar.gz`
* `results/dafny_llm_results_rq1__best_overall.tar.gz`
* `results/dafny_llm_results_rq2__loc_strategy.tar.gz`
* `results/dafny_llm_results_rq3__example_gatherer.tar.gz`
* `results/dafny_llm_results_rq4__different_llms.tar.gz`

### Build the Custom Dafny Binary (Optional if not using Docker)

#### Prerequisites
- .NET SDK 8.0 — [Download](https://dotnet.microsoft.com/en-us/download)
- z3 (version 4.15.4, 64-bit): `sudo dnf install -y z3`

#### Build Dafny
```sh
cd external/dafny_fork
make
```
> **Note:** You may see `FAILURE: Build failed with an exception. Execution failed for task ':javadoc'.` — these do not affect the Dafny binary build. You should see `Build succeeded.` at the end.

### Building the Laurel and Laurel+ Position Inference Strategies

1. **Original Laurel placeholder finder:**
   ```bash
   cd external/dafny_laurel_repair/dafny_laurel_repair/laurel/placeholder_finder
   dotnet build placeholder_finder.csproj
   ```

2. **Laurel+ (improved) placeholder finder:**
   ```bash
   cd external/dafny_laurel_repair/dafny_laurel_repair/laurel/placeholder_finder_laurel_better
   dotnet build placeholder_finder_laurel_better.csproj
   ```

### Install Python Dependencies
```shell
pip install -r src/requirements.txt
```

### Verify the Installation
```sh
PYTHONPATH=src python -m unittest discover -s src/tests -p "test_*.py" -v
```
Some tests may be skipped (those using paid LLM providers). To run them, set `RUN_TEST_THAT_COST_MONEY = True` in `src/utils/global_variables.py`.

---

## Docker

See [README_DOCKER.md](README_DOCKER.md) for Docker-specific instructions.

### Docker Limitations

The verifier can enter unbounded memory loops. Outside Docker, `systemd-run` caps memory usage:
```python
command = ["systemd-run", "--user", "--scope", "-p",
           f"MemoryMax={gl.VERIFIER_MAX_MEMORY}G", str(dafny_exec), ...]
```
Adjust `VERIFIER_MAX_MEMORY` in `src/utils/global_variables.py` (default: 24GB). Must be less than your system memory.

Inside Docker, `systemd-run` is unavailable — a z3 option is used instead (less stable).

---

## Dataset

### Data Structure

#### `dataset/dafny_assertion_all`
```
{file_folder}/assert.xml
{file_folder}/program.dfy
```
- `program.dfy`: The Dafny code
- `assert.xml`: Extracted assertions

#### Example `assert.xml`
```xml
<program>
  <name>example.dfy</name>
  <Method>
    <name>_module._default.example_method</name>
    <start_pos>0</start_pos>
    <end_pos>1448</end_pos>
    <assertion>
      <type>Regular_assertion</type>
      <start_pos>1073</start_pos>
      <end_pos>1118</end_pos>
    </assertion>
  </Method>
</program>
```

#### `dataset/dafny_assertion_dataset`
```
{file_folder}/original_program.dfy
{file_folder}/assertion_group_{id}/info.xml
{file_folder}/assertion_group_{id}/method_without_assertion_group.dfy
{file_folder}/assertion_group_{id}/program_without_assertion_group.dfy
{file_folder}/assertion_group_{id}/verifier_output.txt
```

#### Example `info.xml`
```xml
<method>
  <name>_module._default.testBinarySearch</name>
  <start_pos>946</start_pos>
  <end_pos>1302</end_pos>
  <assertion_group>
    <id>0</id>
    <number_assertions>2</number_assertions>
    <assertion>
      <type>Regular_assertion</type>
      <start_pos>1018</start_pos>
      <end_pos>1050</end_pos>
    </assertion>
  </assertion_group>
</method>
```

---

## Configurations (Extend with More LLMs)

New LLMs can be added in `src/llm/llm_configurations.py`. Each must extend the `LLM` class:
```python
class LLM_my_new_llm(LLM):
    def _get_response(self, prompt: str):
        return "Dummy response"
```

Add a `MODEL_REGISTRY` entry:
```python
"my_new_llm": ModelInfo(
    provider="debug",
    model_id="my_new_llm",
    max_context=128_000,
    cost_1M_in=0,
    cost_1M_out=0
),
```

Then create directly or via factory:
```python
my_new_llm = LLM_my_new_llm("some_name", MODEL_REGISTRY["my_new_llm"])
# or
my_new_llm = create_llm("my_new_llm")  # after adding case to llm_create.py
```

### Running LLM Evaluations
```python
evaluate_all(llm_without_api, global_options, run_options)
```

See `src/llm/llm_pipeline.py` for pipeline options and `src/utils/global_variables.py` for other settings (prompts, etc.).

### Logging and Output Files

All prompts and responses are logged in:
```
dataset/dafny_llm_results/{llm_name}/{file_folder}/{assertion_group_id}/{round_indication}
```

Generated files:
- **previous_program.dfy** — Program tested with missing assertions
- **new_program.dfy** — Program with LLM-generated assertions
- **oracle.dfy** — Fully corrected method/program
- **prompt.txt** — Full prompt sent to the LLM
- **response.txt** — Full response from the LLM
- **verifier_output.txt** — Complete Dafny verifier output
