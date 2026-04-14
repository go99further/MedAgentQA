"""
sample_eval_set.py
==================
Build a stratified evaluation set from the cMedQA2 corpus.

Reads ``data/cmedqa2/questions.csv`` and ``data/cmedqa2/answers.csv``,
performs stratified sampling by the ``department`` column to produce 500
representative questions, pairs each with its top-voted answer, and writes
the result to ``data/eval/eval_set_500.jsonl``.

Usage::

    python -m scripts.sample_eval_set [--n-samples 500] [--seed 42]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("sample_eval_set")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "cmedqa2"
OUTPUT_DIR = PROJECT_ROOT / "data" / "eval"

QUESTIONS_FILE = DATA_DIR / "questions.csv"
ANSWERS_FILE = DATA_DIR / "answers.csv"
OUTPUT_FILE = OUTPUT_DIR / "eval_set_500.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_csv(path: Path, *, required_cols: List[str]) -> pd.DataFrame:
    """Load a CSV with basic validation.

    Supports common encodings found in Chinese medical datasets.
    """
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            df = pd.read_csv(path, encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise RuntimeError(
            f"Failed to read {path} with any supported encoding "
            "(utf-8, utf-8-sig, gb18030, gbk)."
        )

    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )
    logger.info("Loaded %s  --  %d rows, columns: %s", path.name, len(df), list(df.columns))
    return df


def _select_top_answer(
    answers_df: pd.DataFrame,
    question_id: int,
    *,
    vote_col: str = "vote_count",
    qid_col: str = "question_id",
    ans_col: str = "content",
) -> Optional[str]:
    """Return the highest-voted answer text for a given question.

    If *vote_col* is missing the first answer is returned.
    """
    subset = answers_df[answers_df[qid_col] == question_id]
    if subset.empty:
        return None

    if vote_col in subset.columns:
        subset = subset.sort_values(vote_col, ascending=False)

    return str(subset.iloc[0][ans_col])


def _stratified_sample(
    df: pd.DataFrame,
    *,
    n_total: int,
    stratum_col: str = "department",
    seed: int = 42,
) -> pd.DataFrame:
    """Stratified sample of *n_total* rows, proportional to *stratum_col*.

    Departments with fewer rows than their proportional share contribute
    all available rows; the remainder is redistributed to larger departments.
    """
    df = df.copy()
    # Ensure the stratum column has no NaN values for grouping
    df[stratum_col] = df[stratum_col].fillna("unknown")

    counts: Dict[str, int] = df[stratum_col].value_counts().to_dict()
    total_available = sum(counts.values())
    if total_available == 0:
        raise ValueError("No rows available for sampling.")

    n_total = min(n_total, total_available)

    # Proportional allocation with redistribution
    allocation: Dict[str, int] = {}
    remaining = n_total
    unsaturated: List[str] = []

    for dept, cnt in counts.items():
        ideal = int(n_total * cnt / total_available)
        if ideal >= cnt:
            allocation[dept] = cnt
            remaining -= cnt
        else:
            allocation[dept] = ideal
            remaining -= ideal
            unsaturated.append(dept)

    # Distribute leftover to unsaturated departments
    for dept in unsaturated:
        if remaining <= 0:
            break
        room = counts[dept] - allocation[dept]
        extra = min(room, remaining)
        allocation[dept] += extra
        remaining -= extra

    logger.info(
        "Stratified allocation (%d total): %s",
        n_total,
        {k: v for k, v in sorted(allocation.items(), key=lambda x: -x[1])},
    )

    sampled_parts: List[pd.DataFrame] = []
    for dept, n in allocation.items():
        group = df[df[stratum_col] == dept]
        sampled_parts.append(group.sample(n=n, random_state=seed))

    return pd.concat(sampled_parts).sample(frac=1, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_eval_set(
    n_samples: int = 500,
    seed: int = 42,
    output_path: Optional[Path] = None,
) -> Path:
    """Build the evaluation JSONL file and return its path."""
    output_path = output_path or OUTPUT_FILE

    # --- Load data ----------------------------------------------------------
    logger.info("Loading questions from %s", QUESTIONS_FILE)
    # Column names may vary; try common variants
    questions_df = _load_csv(QUESTIONS_FILE, required_cols=["question_id", "content"])
    logger.info("Loading answers from %s", ANSWERS_FILE)
    answers_df = _load_csv(ANSWERS_FILE, required_cols=["question_id", "content"])

    # Ensure department column exists (may be called 'department' or 'dept')
    dept_col = "department"
    if dept_col not in questions_df.columns:
        for alt in ("dept", "科室", "category", "cat"):
            if alt in questions_df.columns:
                questions_df.rename(columns={alt: dept_col}, inplace=True)
                logger.info("Renamed column '%s' -> 'department'", alt)
                break
        else:
            logger.warning(
                "No department column found; falling back to random sampling "
                "without stratification."
            )
            questions_df[dept_col] = "general"

    # --- Stratified sampling ------------------------------------------------
    sampled = _stratified_sample(
        questions_df,
        n_total=n_samples,
        stratum_col=dept_col,
        seed=seed,
    )

    # --- Pair with top-voted answer -----------------------------------------
    # Detect actual column names for answer content and votes
    ans_content_col = "content"
    vote_col = "vote_count"
    for alt in ("answer", "answer_content", "ans"):
        if alt in answers_df.columns and ans_content_col not in answers_df.columns:
            ans_content_col = alt
            break
    for alt in ("votes", "vote", "score", "up_votes"):
        if alt in answers_df.columns and vote_col not in answers_df.columns:
            vote_col = alt
            break

    records: List[Dict] = []
    skipped = 0
    for _, row in sampled.iterrows():
        qid = int(row["question_id"])
        ref_answer = _select_top_answer(
            answers_df,
            qid,
            vote_col=vote_col,
            qid_col="question_id",
            ans_col=ans_content_col,
        )
        if ref_answer is None:
            skipped += 1
            continue
        records.append(
            {
                "question_id": qid,
                "question": str(row["content"]),
                "reference_answer": ref_answer,
                "department": str(row[dept_col]),
            }
        )

    if skipped:
        logger.warning(
            "Skipped %d questions with no matching answer (final count: %d).",
            skipped,
            len(records),
        )

    # --- Write output -------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    logger.info("Wrote %d evaluation records to %s", len(records), output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a stratified evaluation set from cMedQA2."
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=500,
        help="Total number of questions to sample (default: 500).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Override output path (default: data/eval/eval_set_500.jsonl).",
    )
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    try:
        build_eval_set(n_samples=args.n_samples, seed=args.seed, output_path=output)
    except Exception:
        logger.exception("Failed to build evaluation set")
        sys.exit(1)


if __name__ == "__main__":
    main()
