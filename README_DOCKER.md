# Docker Quickstart

Build, load, and run the Docker environment for Daisy.

---

## 1. Install Docker

https://docs.docker.com/engine/install/

Make sure Docker is running before proceeding.

---

## 2. Use a Prebuilt Image

```sh
# Load from archive
docker load -i dafny_research_latest.tar

# Save current image to archive
docker save -o dafny_research_latest.tar dafny_research:latest
```

## 3. Build from Source

```sh
docker build -t dafny_research:latest .
```

## 4. Run a Single File

```sh
docker run --rm -it -w /app dafny_research:latest \
  python -m src.cli myfile.dfy --model cost_stub_almost_real
```

With a dataset example:
```sh
docker run --rm -it -w /app dafny_research:latest \
  python -m src.cli \
    dataset/extracted/dafny_assertion_dataset/SENG2011_tmp_tmpgk5jq85q_exam_ex4_dfy/method_start_0_as_start_197_end_231/program_without_assertion_group.dfy \
    --model cost_stub_almost_real --localization LLM
```

With a real model (pass API key):
```sh
docker run --rm -it \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  -w /app dafny_research:latest \
  python -m src.cli myfile.dfy --model openrouter-free
```

## 5. Interactive Container

```sh
docker run --rm -it \
  -p 8888:8888 \
  -w /app \
  dafny_research:latest bash
```

Inside the container, use the CLI directly:
```sh
python -m src.cli <file.dfy> --model <model> --localization <strategy>
```

## 6. Pass API Keys

```sh
docker run --rm -it \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  -e AWS_BEARER_TOKEN_BEDROCK="$AWS_BEARER_TOKEN_BEDROCK" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  -w /app \
  dafny_research:latest bash
```

## 6. Development Mode (Mount Local Source)

```sh
docker run --rm -it \
  -p 8888:8888 \
  -v "$(pwd)/src:/app/src:delegated" \
  -v "$(pwd)/results:/app/results:delegated" \
  -v "$(pwd)/dataset:/app/dataset:delegated" \
  -v "$(pwd)/tmp:/app/tmp:delegated" \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  -w /app \
  dafny_research:latest bash
```

## 7. Jupyter Notebooks (Data Analysis)

Start the container with port forwarding, then inside:
```sh
jupyter lab --ip=0.0.0.0 --no-browser
```

Copy the URL from the output (looks like `http://127.0.0.1:8888/lab?token=...`) into your browser.

The analysis notebooks are in `src/`:
- `src/data_analysys_rq1_best_overall.ipynb` — RQ1
- `src/data_analysys_rq2_loc_strategy.ipynb` — RQ2
- `src/data_analysys_rq3_example_retrieval.ipynb` — RQ3
- `src/data_analysys_rq4_different_llms.ipynb` — RQ4
- `src/data_analysys_dataset_overview.ipynb` — Dataset overview
- `src/data_analysys_cost_statistics.ipynb` — Cost analysis

## 8. Run Research Scripts

Inside the container:
```sh
python -m src.research_questions.main_rq1
python -m src.research_questions.main_rq2
python -m src.research_questions.main_rq3
```

## 9. Run Tests

```sh
python -m pytest src/tests/ -q
```

## Docker Memory Note

The Dafny verifier can enter unbounded memory loops. Inside Docker, `systemd-run` is unavailable — memory is limited via z3 solver options (`--solver-option:O:memory_max_size=24000`). This is less stable than `systemd-run` but works in containerized environments.
