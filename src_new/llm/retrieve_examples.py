from src_new.llm.extract_error_blocks import extract_error_blocks
from src_new.config import DAFNY_ASSERTION_DATASET
import pickle
import json
from tqdm import tqdm
from pathlib import Path

# Flag — per default do not regenerate dataset embeddings
GENERATE_DATASET_EMBEDDINGS: bool = False

def retrieve_examples(
        cfg : Any,
        method_text: str,
        error_output: str,
        prog_name: str | None = None,
        group_name: str | None = None,
    ) -> list[dict]:
        """Retrieve similar examples from the dataset."""
        filtered_error = extract_error_blocks(error_output)
        entries, model, device, tfidf_vec, tfidf_mat = generate_example_model()

        results = retrieve_by_error_and_code(
            new_error=filtered_error,
            new_code=method_text,
            entries=entries,
            top_k=-1,
            method=cfg.example_retrieval_type,
            α=cfg.example_weight,
            prog_original=prog_name,
            group_original=group_name,
            model=model,
            device=device,
            diferent_methods=1,
            tfidf_vectorizer=tfidf_vec,
            tfidf_matrix=tfidf_mat,
        )

        if cfg.example_retrieval_type == ExampleStrategy.RANDOM:
            import random
            random.shuffle(results)

        return results[: cfg.num_examples]

def format_examples(examples: list[dict]) -> str:
        """Format retrieved examples into a prompt section."""
        if not examples:
            return ""

        parts = ["Consider these examples: \n"]
        for r in examples:
            filtered_error = extract_error_blocks(r["error_message"])
            numbered_lines = "\n".join(
                f"{line_id}: {line}"
                for line_id, line in enumerate(
                    r["method_without_assertion_group"].splitlines()
                )
            )
            parts.append("=== EXAMPLE ===\n")
            parts.append(f"Error:\n{filtered_error}\n")
            parts.append(f"\nCODE:\n{numbered_lines}\n")
            parts.append(f"OUTPUT:\n{r['oracle_pos']}\n")
            parts.append("=== END ===\n")

        return "".join(parts)

# ── Generation ─────────────────────────────────────────────────────────────────
def generate_and_pickle(dataset_dir: Path, model):
    from sentence_transformers import SentenceTransformer
    import torch
    from sentence_transformers.util import cos_sim
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    prog_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
    rows = []
    corpus = []
    for prog_dir in tqdm(prog_dirs, desc="Creating Full dataset Embeddings", total=len(prog_dirs)):
        for grp_dir in prog_dir.iterdir():
            if not grp_dir.is_dir() or grp_dir.name in ("bin", "obj"):
                continue

            error_txt = (grp_dir / "verifier_output.txt").read_text(encoding='utf-8')
            error_txt_filter = extract_error_blocks(error_txt)

            code_txt = (grp_dir / "method_with_assertion_placeholder.dfy").read_text(encoding='utf-8')
            corpus.append(code_txt)

            assertions = str(json.load(open(grp_dir / "oracle_assertions.json")))

            oracle_pos = (grp_dir / "oracle_fix_position.txt").read_text(encoding='utf-8')
            # embed on GPU, then move back to CPU for pickling
            err_emb = model.encode([error_txt_filter], convert_to_tensor=True).cpu()
            cod_emb = model.encode([code_txt], convert_to_tensor=True).cpu()

            # pickle per-group
            with open(grp_dir / "error_embeds.pkl", "wb") as f:
                pickle.dump(err_emb, f)
            with open(grp_dir / "code_embeds.pkl", "wb") as f:
                pickle.dump(cod_emb, f)

            rows.append({
                "prog": prog_dir.name,
                "group": grp_dir.name,
                "error_message": error_txt_filter,
                "code_snippet": code_txt,
                "assertions": assertions,
                "oracle_pos": oracle_pos,
                "error_embeds": err_emb,
                "code_embeds": cod_emb,
                "method_without_assertion_group": (grp_dir / "method_without_assertion_group.dfy").read_text(encoding='utf-8'),
            })

    # After gathering all entries, build TF-IDF
    tfidf_vectorizer = TfidfVectorizer(token_pattern=r"[\w@]+", analyzer="word")
    tfidf_matrix = tfidf_vectorizer.fit_transform(corpus)

    # Save vectorizer and matrix once
    with open(dataset_dir / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf_vectorizer, f)
    with open(dataset_dir / "tfidf_matrix.pkl", "wb") as f:
        pickle.dump(tfidf_matrix, f)

    return rows, tfidf_vectorizer, tfidf_matrix


# ── Loading ────────────────────────────────────────────────────────────────────
def load_entries_from_pickles(dataset_dir: Path):
    entries = []
    prog_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
    for prog_dir in prog_dirs:
        for grp_dir in prog_dir.iterdir():
            if not grp_dir.is_dir() or grp_dir.name in ("bin", "obj"):
                continue

            with open(grp_dir / "error_embeds.pkl", "rb") as f:
                err_emb = pickle.load(f)
            with open(grp_dir / "code_embeds.pkl", "rb") as f:
                cod_emb = pickle.load(f)
            with open(grp_dir / "oracle_assertions.json", "r", encoding="utf-8") as f:
                assertions_data = json.load(f)

            entries.append({
                "prog": prog_dir.name,
                "group": grp_dir.name,
                "error_message": (grp_dir / "verifier_output.txt").read_text(encoding='utf-8'),
                "code_snippet": (grp_dir / "method_with_assertion_placeholder.dfy").read_text(encoding='utf-8'),
                "oracle_pos": (grp_dir / "oracle_fix_position.txt").read_text(encoding='utf-8'),
                "assertions": str(assertions_data),
                "method_without_assertion_group": (grp_dir / "method_without_assertion_group.dfy").read_text(encoding='utf-8'),
                "error_embeds": err_emb,
                "code_embeds": cod_emb,
            })

    with open(dataset_dir / "tfidf_vectorizer.pkl", "rb") as f:
        tfidf_vectorizer = pickle.load(f)
    with open(dataset_dir / "tfidf_matrix.pkl", "rb") as f:
        tfidf_matrix = pickle.load(f)

    return entries, tfidf_vectorizer, tfidf_matrix


# ── Retrieval ──────────────────────────────────────────────────────────────────

def normalize_minmax(sim):
    from sentence_transformers import SentenceTransformer
    import torch
    from sentence_transformers.util import cos_sim
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    minv, maxv = sim.min(), sim.max()
    if maxv - minv > 0:
        return (sim - minv) / (maxv - minv)
    else:
        return torch.zeros_like(sim)


def retrieve_by_error_and_code(
    new_error: str,
    new_code: str,
    entries: list[dict],
    top_k: int = 5,
    method: "str | ExampleStrategy" = "error_code",  # ExampleStrategy enum or legacy string
    α: float = 0.5,
    prog_original=None,
    group_original=None,
    model=None,
    device=None,
    diferent_methods=1,
    tfidf_vectorizer=None,
    tfidf_matrix=None,
):
    from sentence_transformers import SentenceTransformer
    import torch
    from sentence_transformers.util import cos_sim
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from src_new.config import ExampleStrategy as _ES

    # Accept ExampleStrategy enum — resolve to internal string
    if isinstance(method, _ES):
        _ENUM_TO_METHOD = {
            _ES.RANDOM: "embedding",
            _ES.TFIDF: "tfidf",
            _ES.EMBEDDED: "embedding",
            _ES.DYNAMIC: "error_code",
        }
        method = _ENUM_TO_METHOD.get(method, method.value.lower())

    if top_k == -1:
        top_k = len(entries)

    if method == "tfidf":
        if tfidf_vectorizer is None or tfidf_matrix is None:
            raise ValueError("tfidf_vectorizer and tfidf_matrix must be provided for tfidf method")

        q_vec = tfidf_vectorizer.transform([new_code])
        sims = cosine_similarity(q_vec, tfidf_matrix).flatten()
        scores = torch.tensor(sims)
        idxs = torch.topk(scores, k=top_k).indices.tolist()
        selected_scores = scores[idxs].tolist()
    else:
        q_cod = model.encode([new_code], convert_to_tensor=True).to(device)
        all_codes = torch.cat([e["code_embeds"] for e in entries], dim=0).to(device)
        sim_cod = cos_sim(q_cod, all_codes)[0]
        sim_cod_n = normalize_minmax(sim_cod)

        if method == "embedding":
            combined = sim_cod_n
        else:
            q_err = model.encode([new_error], convert_to_tensor=True).to(device)
            all_errs = torch.cat([e["error_embeds"] for e in entries], dim=0).to(device)
            sim_err = cos_sim(q_err, all_errs)[0]
            sim_err_n = normalize_minmax(sim_err)
            combined = α * sim_err_n + (1 - α) * sim_cod_n
        idxs = torch.topk(combined, k=top_k).indices.tolist()
        selected_scores = combined[idxs].tolist()

    if prog_original and group_original:
        _, _, orig_method_start, *_ = group_original.split("_", 3)
    else:
        orig_method_start = None

    results = []
    inserted_progs = []
    for i, score in zip(idxs, selected_scores):
        e = entries[i]
        if prog_original and group_original:
            _, _, method_start, *_ = e["group"].split("_", 3)
            if diferent_methods == 1 and (e["prog"], method_start) in inserted_progs:
                continue
            if e["prog"] == prog_original:
                _, _, method_startstart, *_ = e["group"].split("_", 3)
                if method_start == orig_method_start:
                    continue

            inserted_progs.append((e["prog"], method_start))

        results.append({
            "prog": e["prog"],
            "group": e["group"],
            "score": score,
            "error_message": e["error_message"],
            "code_snippet": e["code_snippet"],
            "assertions": e["assertions"],
            "oracle_pos": e["oracle_pos"],
            "method_without_assertion_group": e['method_without_assertion_group'],
        })
    return results


def generate_example_model():
    from sentence_transformers import SentenceTransformer
    import torch
    from sentence_transformers.util import cos_sim
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    if not hasattr(generate_example_model, "_entries"):
        DATASET_DIR = Path(DAFNY_ASSERTION_DATASET)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = SentenceTransformer(
            'jinaai/jina-embeddings-v2-base-code',
            trust_remote_code=True,
            device=device,
        )
        generate_example_model._model = model
        generate_example_model._device = device
        if GENERATE_DATASET_EMBEDDINGS:
            generate_example_model._entries, generate_example_model._tfidf_vectorizer, generate_example_model._tfidf_matrix = generate_and_pickle(DATASET_DIR, model)
        else:
            try:
                generate_example_model._entries, generate_example_model._tfidf_vectorizer, generate_example_model._tfidf_matrix = load_entries_from_pickles(DATASET_DIR)
            except Exception:
                generate_example_model._entries, generate_example_model._tfidf_vectorizer, generate_example_model._tfidf_matrix = generate_and_pickle(DATASET_DIR, model)

    return generate_example_model._entries, generate_example_model._model, generate_example_model._device, generate_example_model._tfidf_vectorizer, generate_example_model._tfidf_matrix
