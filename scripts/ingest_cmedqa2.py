"""
ingest_cmedqa2.py
=================
Ingest cMedQA2 medical QA data into Milvus (vector store) and optionally
into pgvector via the ``kb_ingest`` HTTP service.

Workflow
--------
1. Load ``questions.csv`` and ``answers.csv`` from the cMedQA2 data directory.
2. Merge questions with their answers; optionally rank by length / vote count.
3. Chunk answer texts using :class:`RecursiveCharacterTextSplitter` with
   Chinese-aware separators.
4. Generate embeddings via an OpenAI-compatible API.
5. Upsert chunks + embeddings into **Milvus**.
6. POST the top-K highest-quality answers to a ``kb_ingest`` service for
   storage in **pgvector**.

Environment variables
---------------------
``EMBEDDING_BASE_URL``
    Base URL of the embedding API (default: ``None`` -- uses OpenAI).
``EMBEDDING_API_KEY``
    API key for the embedding service.
``EMBEDDING_MODEL``
    Model identifier (default: ``text-embedding-3-small``).
``EMBEDDING_DIMENSION``
    Expected vector dimension (default: ``1536``).
``KB_INGEST_URL``
    Base URL of the kb_ingest service (default: ``http://localhost:8000``).

Usage::

    python -m scripts.ingest_cmedqa2 --data-dir data/cmedqa2
    python -m scripts.ingest_cmedqa2 --dry-run --top-k-pg 3000
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

import pandas as pd
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("ingest_cmedqa2")

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "cmedqa2"

MILVUS_COLLECTION_NAME = "cmedqa2"
EMBEDDING_DIMENSION_DEFAULT = 1536

CHINESE_SEPARATORS: List[str] = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    "，",
    "、",
    " ",
    "",
]

MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # seconds


# ---------------------------------------------------------------------------
# CSV loader (multi-encoding)
# ---------------------------------------------------------------------------


def load_csv(path: Path, *, required_cols: List[str]) -> pd.DataFrame:
    """Load a CSV trying several encodings common in Chinese datasets.

    Parameters
    ----------
    path:
        Filesystem path to the CSV file.
    required_cols:
        Column names that must exist after loading.

    Returns
    -------
    pd.DataFrame
        The loaded dataframe.

    Raises
    ------
    RuntimeError
        If none of the candidate encodings can decode the file.
    ValueError
        If required columns are missing.
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
    logger.info(
        "Loaded %s  --  %d rows, columns: %s",
        path.name,
        len(df),
        list(df.columns),
    )
    return df


# ---------------------------------------------------------------------------
# Embedding client with retry
# ---------------------------------------------------------------------------


class EmbeddingClient:
    """Thin wrapper around the OpenAI embeddings API with retry logic."""

    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dimension: int = EMBEDDING_DIMENSION_DEFAULT,
        max_batch_size: int = 64,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.max_batch_size = max_batch_size
        self.timeout = timeout

        client_kwargs: Dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)
        logger.info(
            "Embedding client initialised (model=%s, base_url=%s, dim=%d)",
            model,
            base_url or "https://api.openai.com/v1",
            dimension,
        )

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts with retry logic.

        Parameters
        ----------
        texts:
            Strings to embed.  Empty/blank strings are replaced with a
            single space to avoid upstream errors.

        Returns
        -------
        List[List[float]]
            One embedding vector per input text.
        """
        sanitised = [(t or "").strip() or " " for t in texts]
        all_vectors: List[List[float]] = []

        for start in range(0, len(sanitised), self.max_batch_size):
            batch = sanitised[start : start + self.max_batch_size]
            vectors = self._call_with_retry(batch)
            all_vectors.extend(vectors)

        if len(all_vectors) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: expected {len(texts)}, "
                f"got {len(all_vectors)}"
            )
        return all_vectors

    def _call_with_retry(self, batch: List[str]) -> List[List[float]]:
        """Call the embeddings endpoint with exponential-backoff retry."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                    timeout=self.timeout,
                )
                return [list(item.embedding) for item in resp.data]
            except Exception as exc:
                last_exc = exc
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    "Embedding API call failed (attempt %d/%d): %s  "
                    "-- retrying in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Embedding API failed after {MAX_RETRIES} retries"
        ) from last_exc


# ---------------------------------------------------------------------------
# Milvus helpers
# ---------------------------------------------------------------------------


def _ensure_milvus_collection(
    host: str,
    port: int,
    dimension: int,
) -> Collection:
    """Connect to Milvus and create / load the cMedQA2 collection.

    The collection schema stores:
    - ``id``: primary key (VARCHAR)
    - ``embedding``: float vector
    - ``content``: chunk text
    - ``question_id``: source question id
    - ``answer_id``: source answer id
    - ``department``: medical department

    Returns
    -------
    Collection
        The ready-to-use Milvus collection.
    """
    connections.connect(alias="default", host=host, port=port)
    logger.info("Connected to Milvus at %s:%d", host, port)

    if utility.has_collection(MILVUS_COLLECTION_NAME):
        col = Collection(MILVUS_COLLECTION_NAME)
        logger.info("Using existing Milvus collection '%s'", MILVUS_COLLECTION_NAME)
    else:
        fields = [
            FieldSchema(
                name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256
            ),
            FieldSchema(
                name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension
            ),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(
                name="question_id", dtype=DataType.VARCHAR, max_length=64
            ),
            FieldSchema(
                name="answer_id", dtype=DataType.VARCHAR, max_length=64
            ),
            FieldSchema(
                name="department", dtype=DataType.VARCHAR, max_length=128
            ),
        ]
        schema = CollectionSchema(
            fields=fields,
            description="cMedQA2 medical QA knowledge base",
        )
        col = Collection(name=MILVUS_COLLECTION_NAME, schema=schema)

        col.create_index(
            field_name="embedding",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "IP",
                "params": {"nlist": 128},
            },
        )
        logger.info(
            "Created Milvus collection '%s' (dim=%d)", MILVUS_COLLECTION_NAME, dimension
        )

    col.load()
    return col


def insert_milvus_batch(
    collection: Collection,
    *,
    ids: List[str],
    embeddings: List[List[float]],
    contents: List[str],
    question_ids: List[str],
    answer_ids: List[str],
    departments: List[str],
) -> int:
    """Insert a batch of chunks into Milvus.

    Returns
    -------
    int
        Number of rows actually inserted.
    """
    entities = [
        ids,
        embeddings,
        contents,
        question_ids,
        answer_ids,
        departments,
    ]
    collection.insert(entities)
    collection.flush()
    return len(ids)


# ---------------------------------------------------------------------------
# pgvector / kb_ingest HTTP helper
# ---------------------------------------------------------------------------


def post_to_kb_ingest(
    base_url: str,
    *,
    doc_id: str,
    title: str,
    content: str,
    metadata: Dict[str, Any],
) -> bool:
    """POST a single document to the kb_ingest service for pgvector storage.

    Parameters
    ----------
    base_url:
        Root URL of the kb_ingest service, e.g. ``http://localhost:8000``.
    doc_id:
        Unique identifier for the document.
    title:
        Short title / question text.
    content:
        Full answer text.
    metadata:
        Extra metadata to attach to the document.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure (logged, not raised).
    """
    url = f"{base_url.rstrip('/')}/api/v1/knowledge/documents"
    payload = {
        "doc_id": doc_id,
        "title": title,
        "content": content,
        "metadata": metadata,
    }

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            last_exc = exc
            wait = BACKOFF_BASE ** attempt
            logger.warning(
                "kb_ingest POST failed (attempt %d/%d): %s  -- retrying in %.1fs",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)

    logger.error("kb_ingest POST failed after %d retries: %s", MAX_RETRIES, last_exc)
    return False


# ---------------------------------------------------------------------------
# Chunk ID generation
# ---------------------------------------------------------------------------


def _chunk_id(question_id: str, answer_id: str, chunk_index: int) -> str:
    """Produce a deterministic chunk ID for deduplication."""
    raw = f"cmedqa2-q{question_id}-a{answer_id}-c{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------


def ingest(
    *,
    data_dir: Path,
    milvus_host: str,
    milvus_port: int,
    batch_size: int,
    dry_run: bool,
    top_k_pg: int,
    kb_ingest_url: str,
    embedding_model: str,
    embedding_api_key: Optional[str],
    embedding_base_url: Optional[str],
    embedding_dimension: int,
) -> Dict[str, Any]:
    """Run the full ingestion pipeline.

    Parameters
    ----------
    data_dir:
        Directory containing ``questions.csv`` and ``answers.csv``.
    milvus_host:
        Milvus server hostname.
    milvus_port:
        Milvus server port.
    batch_size:
        Number of chunks to embed / insert per batch.
    dry_run:
        If ``True``, load and chunk data but skip all writes.
    top_k_pg:
        Number of top-quality answers to push to pgvector.
    kb_ingest_url:
        Base URL of the kb_ingest HTTP service.
    embedding_model:
        Model identifier for the embedding API.
    embedding_api_key:
        API key for the embedding service.
    embedding_base_url:
        Base URL for the embedding service.
    embedding_dimension:
        Expected vector dimension.

    Returns
    -------
    dict
        Summary statistics of the run.
    """
    t0 = time.time()

    stats: Dict[str, Any] = {
        "total_questions": 0,
        "total_answers": 0,
        "total_chunks": 0,
        "total_embeddings": 0,
        "milvus_inserted": 0,
        "pg_posted": 0,
        "pg_errors": 0,
        "embed_errors": 0,
        "elapsed_seconds": 0.0,
    }

    # ---- 1. Load CSVs ------------------------------------------------------
    questions_file = data_dir / "questions.csv"
    answers_file = data_dir / "answers.csv"

    if not questions_file.exists():
        logger.error("Questions file not found: %s", questions_file)
        sys.exit(1)
    if not answers_file.exists():
        logger.error("Answers file not found: %s", answers_file)
        sys.exit(1)

    questions_df = load_csv(questions_file, required_cols=["question_id", "content"])
    answers_df = load_csv(answers_file, required_cols=["question_id", "content"])

    stats["total_questions"] = len(questions_df)
    stats["total_answers"] = len(answers_df)

    # Detect column names for answer content
    ans_content_col = "content"
    for alt in ("answer", "answer_content", "ans"):
        if alt in answers_df.columns and ans_content_col not in answers_df.columns:
            ans_content_col = alt
            break

    # Detect vote column
    vote_col: Optional[str] = None
    for candidate in ("vote_count", "votes", "vote", "score", "up_votes"):
        if candidate in answers_df.columns:
            vote_col = candidate
            break

    # Detect answer_id column
    ans_id_col: Optional[str] = None
    for candidate in ("answer_id", "ans_id", "id"):
        if candidate in answers_df.columns:
            ans_id_col = candidate
            break

    # Detect department column on questions
    dept_col: Optional[str] = None
    for candidate in ("department", "dept", "category"):
        if candidate in questions_df.columns:
            dept_col = candidate
            break

    # ---- 2. Merge questions + answers --------------------------------------
    merged = answers_df.merge(
        questions_df[["question_id", "content"] + ([dept_col] if dept_col else [])],
        on="question_id",
        how="inner",
        suffixes=("_answer", "_question"),
    )

    # Resolve content columns after merge
    q_content_col = "content_question" if "content_question" in merged.columns else "content"
    a_content_col = (
        "content_answer"
        if "content_answer" in merged.columns
        else ans_content_col
    )

    logger.info(
        "Merged dataset: %d answer-question pairs", len(merged)
    )

    # ---- 3. Chunk answers --------------------------------------------------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=384,
        chunk_overlap=50,
        separators=CHINESE_SEPARATORS,
        length_function=len,
    )

    all_chunks: List[Dict[str, Any]] = []
    for _, row in tqdm(merged.iterrows(), total=len(merged), desc="Chunking answers"):
        answer_text = str(row.get(a_content_col, "") or "").strip()
        if not answer_text:
            continue

        question_text = str(row.get(q_content_col, "") or "").strip()
        q_id = str(row["question_id"])
        a_id = str(row[ans_id_col]) if ans_id_col and pd.notna(row.get(ans_id_col)) else uuid4().hex[:12]
        department = str(row.get(dept_col, "")) if dept_col else ""

        chunks = splitter.split_text(answer_text)
        for ci, chunk_text in enumerate(chunks):
            all_chunks.append(
                {
                    "chunk_id": _chunk_id(q_id, a_id, ci),
                    "content": chunk_text,
                    "question_id": q_id,
                    "answer_id": a_id,
                    "question_text": question_text,
                    "department": department,
                }
            )

    stats["total_chunks"] = len(all_chunks)
    logger.info("Total chunks produced: %d", len(all_chunks))

    if dry_run:
        logger.info("[DRY-RUN] Skipping Milvus insertion and embedding generation.")
        stats["elapsed_seconds"] = round(time.time() - t0, 2)
        return stats

    # ---- 4. Embed + insert into Milvus in batches --------------------------
    embedder = EmbeddingClient(
        model=embedding_model,
        api_key=embedding_api_key,
        base_url=embedding_base_url,
        dimension=embedding_dimension,
    )

    collection = _ensure_milvus_collection(
        host=milvus_host,
        port=milvus_port,
        dimension=embedding_dimension,
    )

    for batch_start in tqdm(
        range(0, len(all_chunks), batch_size),
        desc="Embedding & inserting",
        total=(len(all_chunks) + batch_size - 1) // batch_size,
    ):
        batch = all_chunks[batch_start : batch_start + batch_size]
        texts = [c["content"] for c in batch]

        try:
            vectors = embedder.embed_batch(texts)
            stats["total_embeddings"] += len(vectors)
        except Exception:
            logger.exception(
                "Failed to embed batch starting at index %d", batch_start
            )
            stats["embed_errors"] += len(batch)
            continue

        inserted = insert_milvus_batch(
            collection,
            ids=[c["chunk_id"] for c in batch],
            embeddings=vectors,
            contents=texts,
            question_ids=[c["question_id"] for c in batch],
            answer_ids=[c["answer_id"] for c in batch],
            departments=[c["department"] for c in batch],
        )
        stats["milvus_inserted"] += inserted

    logger.info(
        "Milvus ingestion complete: %d chunks inserted", stats["milvus_inserted"]
    )

    # ---- 5. Select top-K answers for pgvector ------------------------------
    if top_k_pg > 0:
        logger.info(
            "Selecting top %d high-quality answers for pgvector...", top_k_pg
        )
        _push_top_answers_to_pg(
            merged=merged,
            a_content_col=a_content_col,
            q_content_col=q_content_col,
            ans_id_col=ans_id_col,
            dept_col=dept_col,
            vote_col=vote_col,
            top_k=top_k_pg,
            kb_ingest_url=kb_ingest_url,
            stats=stats,
        )

    # ---- 6. Done -----------------------------------------------------------
    try:
        connections.disconnect("default")
    except Exception:
        pass

    stats["elapsed_seconds"] = round(time.time() - t0, 2)
    return stats


# ---------------------------------------------------------------------------
# pgvector top-K helper
# ---------------------------------------------------------------------------


def _push_top_answers_to_pg(
    *,
    merged: pd.DataFrame,
    a_content_col: str,
    q_content_col: str,
    ans_id_col: Optional[str],
    dept_col: Optional[str],
    vote_col: Optional[str],
    top_k: int,
    kb_ingest_url: str,
    stats: Dict[str, Any],
) -> None:
    """Rank answers by quality and POST the top-K to the kb_ingest service.

    Quality heuristic: sort by ``vote_count`` descending (if available),
    then by answer text length descending.  Longer, well-voted answers are
    assumed to be higher quality.
    """
    df = merged.copy()

    # Add answer length column for ranking
    df["_answer_len"] = df[a_content_col].astype(str).str.len()

    sort_cols: List[str] = []
    ascending: List[bool] = []

    if vote_col and vote_col in df.columns:
        df[vote_col] = pd.to_numeric(df[vote_col], errors="coerce").fillna(0)
        sort_cols.append(vote_col)
        ascending.append(False)

    sort_cols.append("_answer_len")
    ascending.append(False)

    df = df.sort_values(sort_cols, ascending=ascending).head(top_k)

    logger.info("Posting %d answers to kb_ingest at %s", len(df), kb_ingest_url)

    for _, row in tqdm(df.iterrows(), total=len(df), desc="pgvector POST"):
        q_id = str(row["question_id"])
        a_id = (
            str(row[ans_id_col])
            if ans_id_col and pd.notna(row.get(ans_id_col))
            else uuid4().hex[:12]
        )
        question_text = str(row.get(q_content_col, "") or "")
        answer_text = str(row.get(a_content_col, "") or "")
        department = str(row.get(dept_col, "")) if dept_col else ""

        doc_id = f"cmedqa2-q{q_id}-a{a_id}"
        metadata: Dict[str, Any] = {
            "source": "cmedqa2",
            "question_id": q_id,
            "answer_id": a_id,
            "department": department,
        }

        ok = post_to_kb_ingest(
            kb_ingest_url,
            doc_id=doc_id,
            title=question_text[:200],
            content=answer_text,
            metadata=metadata,
        )
        if ok:
            stats["pg_posted"] += 1
        else:
            stats["pg_errors"] += 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest cMedQA2 medical QA data into Milvus and pgvector.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing questions.csv and answers.csv.",
    )
    parser.add_argument(
        "--milvus-host",
        type=str,
        default=os.getenv("MILVUS_HOST", "localhost"),
        help="Milvus server hostname.",
    )
    parser.add_argument(
        "--milvus-port",
        type=int,
        default=int(os.getenv("MILVUS_PORT", "19530")),
        help="Milvus server port.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Number of chunks to embed / insert per batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Load and chunk data without writing to any store.",
    )
    parser.add_argument(
        "--top-k-pg",
        type=int,
        default=5000,
        help="Number of top-quality answers to push to pgvector.",
    )
    parser.add_argument(
        "--kb-ingest-url",
        type=str,
        default=os.getenv("KB_INGEST_URL", "http://localhost:8000"),
        help="Base URL of the kb_ingest HTTP service.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    args = parse_args(argv)

    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key = os.getenv("EMBEDDING_API_KEY")
    embedding_base_url = os.getenv("EMBEDDING_BASE_URL")
    embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    logger.info("=" * 60)
    logger.info("cMedQA2 Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info("  data_dir        : %s", args.data_dir)
    logger.info("  milvus          : %s:%d", args.milvus_host, args.milvus_port)
    logger.info("  batch_size      : %d", args.batch_size)
    logger.info("  dry_run         : %s", args.dry_run)
    logger.info("  top_k_pg        : %d", args.top_k_pg)
    logger.info("  embedding_model : %s", embedding_model)
    logger.info("  embedding_dim   : %d", embedding_dimension)
    logger.info("=" * 60)

    try:
        stats = ingest(
            data_dir=Path(args.data_dir),
            milvus_host=args.milvus_host,
            milvus_port=args.milvus_port,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            top_k_pg=args.top_k_pg,
            kb_ingest_url=args.kb_ingest_url,
            embedding_model=embedding_model,
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
            embedding_dimension=embedding_dimension,
        )
    except Exception:
        logger.exception("Ingestion pipeline failed")
        sys.exit(1)

    # ---- Summary -----------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("  INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info("  Questions loaded   : %d", stats["total_questions"])
    logger.info("  Answers loaded     : %d", stats["total_answers"])
    logger.info("  Chunks produced    : %d", stats["total_chunks"])
    logger.info("  Embeddings created : %d", stats["total_embeddings"])
    logger.info("  Milvus inserted    : %d", stats["milvus_inserted"])
    logger.info("  pgvector posted    : %d", stats["pg_posted"])
    logger.info("  pgvector errors    : %d", stats["pg_errors"])
    logger.info("  Embedding errors   : %d", stats["embed_errors"])
    logger.info("  Elapsed time       : %.1fs", stats["elapsed_seconds"])
    logger.info("=" * 60)

    total_errors = stats["embed_errors"] + stats["pg_errors"]
    if total_errors > 0:
        logger.warning("Completed with %d error(s).", total_errors)
        sys.exit(2)

    logger.info("Ingestion completed successfully.")


if __name__ == "__main__":
    main()
