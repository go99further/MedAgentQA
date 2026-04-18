"""
ingest_chimedqa2.py
===================
Ingest ChiMed 2.0 (Huatuo-Encyclopedia-QA) medical QA data into Milvus
and optionally into pgvector via the ``kb_ingest`` HTTP service.

Workflow
--------
1. Load data from HuggingFace or a local CSV file.
2. Clean answers: remove blanks, pure-numeric, and abnormally long entries.
3. Chunk answer texts using RecursiveCharacterTextSplitter with Chinese-aware separators.
4. Generate embeddings via an OpenAI-compatible API.
5. Upsert chunks + embeddings into **Milvus** (collection: ``chimedqa2``).
6. Optionally POST top-K answers to a ``kb_ingest`` service for pgvector storage.

Usage::

    # Dry-run: confirm field names and data shape
    python scripts/ingest_chimedqa2.py --dry-run --n-samples 10

    # Small batch to validate pipeline
    python scripts/ingest_chimedqa2.py --n-samples 500

    # Full ingestion (skip pgvector, Milvus only)
    python scripts/ingest_chimedqa2.py --skip-pgvector

    # From local CSV
    python scripts/ingest_chimedqa2.py --source /path/to/chimedqa2.csv
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
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
logger = logging.getLogger("ingest_chimedqa2")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_COLLECTION_NAME = "chimedqa2"
EMBEDDING_DIMENSION_DEFAULT = 1536

CHINESE_SEPARATORS: List[str] = [
    "\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", "",
]

MAX_RETRIES = 3
BACKOFF_BASE = 2.0

# Answer quality filters
MIN_ANSWER_LEN = 20       # characters — skip near-empty answers
MAX_ANSWER_LEN = 2000     # characters — skip abnormally long (likely scrape errors)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_chimedqa2(source: str, n_samples: Optional[int] = None) -> pd.DataFrame:
    """Load ChiMed 2.0 data from HuggingFace or a local CSV.

    Parameters
    ----------
    source:
        ``"huggingface"`` to download from HuggingFace, or a local file path.
    n_samples:
        If set, return only the first N rows (useful for testing).

    Returns
    -------
    pd.DataFrame
        Columns: ``question``, ``answer``, ``department`` (may be empty string).
    """
    if source == "huggingface":
        try:
            from datasets import load_dataset
        except ImportError:
            logger.error(
                "The 'datasets' package is required for HuggingFace loading. "
                "Install it with: pip install datasets"
            )
            sys.exit(1)

        logger.info("Downloading FreedomIntelligence/Huatuo-Encyclopedia-QA from HuggingFace...")
        ds = load_dataset("FreedomIntelligence/Huatuo-Encyclopedia-QA", split="train")
        logger.info("Dataset loaded. Columns: %s  |  Rows: %d", ds.column_names, len(ds))
        df = ds.to_pandas()
    else:
        path = Path(source)
        if not path.exists():
            logger.error("File not found: %s", path)
            sys.exit(1)
        df = _load_csv(path, required_cols=["question", "answer"])

    # Normalise column names: some versions use 'knowledge' instead of 'answer'
    if "answer" not in df.columns and "knowledge" in df.columns:
        df = df.rename(columns={"knowledge": "answer"})
        logger.info("Renamed column 'knowledge' → 'answer'")

    if "question" not in df.columns or "answer" not in df.columns:
        logger.error(
            "Required columns 'question' and 'answer' not found. "
            "Available columns: %s", list(df.columns)
        )
        sys.exit(1)

    if "department" not in df.columns:
        df["department"] = ""

    df = df[["question", "answer", "department"]].copy()
    df["question"] = df["question"].fillna("").astype(str)
    df["answer"] = df["answer"].fillna("").astype(str)
    df["department"] = df["department"].fillna("").astype(str)

    if n_samples:
        df = df.head(n_samples)

    logger.info("Loaded %d rows", len(df))
    return df


def _load_csv(path: Path, *, required_cols: List[str]) -> pd.DataFrame:
    """Load a CSV trying several encodings common in Chinese datasets."""
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
    logger.info("Loaded %s — %d rows, columns: %s", path.name, len(df), list(df.columns))
    return df


def _clean_answers(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out low-quality answers.

    Removes:
    - Answers shorter than MIN_ANSWER_LEN (blank / near-empty)
    - Answers longer than MAX_ANSWER_LEN (likely scrape errors)
    - Answers that are purely numeric
    """
    before = len(df)
    df = df[df["answer"].str.strip().str.len() >= MIN_ANSWER_LEN]
    df = df[df["answer"].str.len() <= MAX_ANSWER_LEN]
    df = df[~df["answer"].str.strip().str.match(r"^\d+$")]
    after = len(df)
    logger.info("Quality filter: %d → %d rows (removed %d)", before, after, before - after)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Embedding client (same as ingest_cmedqa2.py)
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
            model, base_url or "https://api.openai.com/v1", dimension,
        )

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        sanitised = [(t or "").strip() or " " for t in texts]
        all_vectors: List[List[float]] = []
        for start in range(0, len(sanitised), self.max_batch_size):
            batch = sanitised[start: start + self.max_batch_size]
            all_vectors.extend(self._call_with_retry(batch))
        if len(all_vectors) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(all_vectors)}"
            )
        return all_vectors

    def _call_with_retry(self, batch: List[str]) -> List[List[float]]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.embeddings.create(
                    model=self.model, input=batch, timeout=self.timeout
                )
                return [list(item.embedding) for item in resp.data]
            except Exception as exc:
                last_exc = exc
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    "Embedding API failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        raise RuntimeError(f"Embedding API failed after {MAX_RETRIES} retries") from last_exc


# ---------------------------------------------------------------------------
# Milvus helpers
# ---------------------------------------------------------------------------

def _ensure_milvus_collection(
    host: str,
    port: int,
    dimension: int,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Collection:
    """Connect to Milvus and create / load the chimedqa2 collection."""
    connections.connect(alias="default", host=host, port=port)
    logger.info("Connected to Milvus at %s:%d", host, port)

    if utility.has_collection(collection_name):
        col = Collection(collection_name)
        logger.info("Using existing Milvus collection '%s'", collection_name)
    else:
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="question_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="answer_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="department", dtype=DataType.VARCHAR, max_length=128),
        ]
        schema = CollectionSchema(
            fields=fields,
            description="ChiMed 2.0 (Huatuo-Encyclopedia-QA) medical knowledge base",
        )
        col = Collection(name=collection_name, schema=schema)
        col.create_index(
            field_name="embedding",
            index_params={"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}},
        )
        logger.info("Created Milvus collection '%s' (dim=%d)", collection_name, dimension)

    col.load()
    return col


def _insert_milvus_batch(
    collection: Collection,
    *,
    ids: List[str],
    embeddings: List[List[float]],
    contents: List[str],
    question_ids: List[str],
    answer_ids: List[str],
    departments: List[str],
) -> int:
    entities = [ids, embeddings, contents, question_ids, answer_ids, departments]
    collection.insert(entities)
    collection.flush()
    return len(ids)


# ---------------------------------------------------------------------------
# pgvector helper
# ---------------------------------------------------------------------------

def _post_to_kb_ingest(
    base_url: str,
    *,
    doc_id: str,
    title: str,
    content: str,
    metadata: Dict[str, Any],
) -> bool:
    import requests
    url = f"{base_url.rstrip('/')}/api/v1/knowledge/documents"
    payload = {"doc_id": doc_id, "title": title, "content": content, "metadata": metadata}
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return True
        except Exception as exc:
            last_exc = exc
            wait = BACKOFF_BASE ** attempt
            logger.warning(
                "kb_ingest POST failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    logger.error("kb_ingest POST failed after %d retries: %s", MAX_RETRIES, last_exc)
    return False


# ---------------------------------------------------------------------------
# Chunk ID
# ---------------------------------------------------------------------------

def _chunk_id(row_index: int, chunk_index: int) -> str:
    raw = f"chimedqa2-r{row_index}-c{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest(
    *,
    source: str,
    milvus_host: str,
    milvus_port: int,
    collection_name: str,
    batch_size: int,
    dry_run: bool,
    skip_pgvector: bool,
    top_k_pg: int,
    kb_ingest_url: str,
    embedding_model: str,
    embedding_api_key: Optional[str],
    embedding_base_url: Optional[str],
    embedding_dimension: int,
    n_samples: Optional[int] = None,
) -> Dict[str, Any]:
    t0 = time.time()
    stats: Dict[str, Any] = {
        "total_rows": 0,
        "total_chunks": 0,
        "milvus_inserted": 0,
        "pg_posted": 0,
        "pg_errors": 0,
        "embed_errors": 0,
        "elapsed_seconds": 0.0,
    }

    # 1. Load and clean data
    df = load_chimedqa2(source, n_samples)
    df = _clean_answers(df)
    stats["total_rows"] = len(df)

    if dry_run:
        logger.info("[DRY RUN] First 3 rows:")
        for _, row in df.head(3).iterrows():
            logger.info("  Q: %s", row["question"][:80])
            logger.info("  A: %s", row["answer"][:120])
            logger.info("  dept: %s", row["department"])
        logger.info("[DRY RUN] Skipping all writes. Stats: %s", stats)
        return stats

    # 2. Init embedding client
    embed_client = EmbeddingClient(
        model=embedding_model,
        api_key=embedding_api_key,
        base_url=embedding_base_url,
        dimension=embedding_dimension,
    )

    # 3. Init Milvus
    collection = _ensure_milvus_collection(
        milvus_host, milvus_port, embedding_dimension, collection_name
    )

    # 4. Text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=384,
        chunk_overlap=50,
        separators=CHINESE_SEPARATORS,
    )

    # 5. Chunk, embed, insert
    ids_buf: List[str] = []
    emb_buf: List[List[float]] = []
    content_buf: List[str] = []
    qid_buf: List[str] = []
    aid_buf: List[str] = []
    dept_buf: List[str] = []

    def _flush():
        if not ids_buf:
            return
        inserted = _insert_milvus_batch(
            collection,
            ids=ids_buf, embeddings=emb_buf, contents=content_buf,
            question_ids=qid_buf, answer_ids=aid_buf, departments=dept_buf,
        )
        stats["milvus_inserted"] += inserted
        ids_buf.clear(); emb_buf.clear(); content_buf.clear()
        qid_buf.clear(); aid_buf.clear(); dept_buf.clear()

    for row_idx, row in tqdm(df.iterrows(), total=len(df), desc="Ingesting"):
        question = row["question"]
        answer = row["answer"]
        department = row["department"]
        row_id = str(row_idx)

        chunks = splitter.split_text(answer)
        if not chunks:
            continue

        try:
            vectors = embed_client.embed_batch(chunks)
        except Exception as exc:
            logger.warning("Embedding failed for row %d: %s — skipping", row_idx, exc)
            stats["embed_errors"] += 1
            continue

        for chunk_idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            cid = _chunk_id(row_idx, chunk_idx)
            ids_buf.append(cid)
            emb_buf.append(vec)
            content_buf.append(chunk[:65535])
            qid_buf.append(row_id)
            aid_buf.append(row_id)
            dept_buf.append(department[:128])
            stats["total_chunks"] += 1

        if len(ids_buf) >= batch_size:
            _flush()

    _flush()

    # 6. Optional pgvector POST (top-K by answer length)
    if not skip_pgvector:
        logger.info("Posting top-%d answers to pgvector...", top_k_pg)
        top_df = df.copy()
        top_df["answer_len"] = top_df["answer"].str.len()
        top_df = top_df.nlargest(top_k_pg, "answer_len")
        for row_idx, row in tqdm(top_df.iterrows(), total=len(top_df), desc="pgvector"):
            ok = _post_to_kb_ingest(
                kb_ingest_url,
                doc_id=f"chimedqa2-{row_idx}",
                title=row["question"][:512],
                content=row["answer"],
                metadata={"department": row["department"], "source": "chimedqa2"},
            )
            if ok:
                stats["pg_posted"] += 1
            else:
                stats["pg_errors"] += 1

    stats["elapsed_seconds"] = round(time.time() - t0, 1)
    logger.info("Ingestion complete: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest ChiMed 2.0 (Huatuo-Encyclopedia-QA) into Milvus."
    )
    parser.add_argument(
        "--source", default="huggingface",
        help="'huggingface' or path to local CSV (default: huggingface)",
    )
    parser.add_argument(
        "--n-samples", type=int, default=None,
        help="Limit ingestion to first N rows (default: all)",
    )
    parser.add_argument(
        "--milvus-collection", default=DEFAULT_COLLECTION_NAME,
        help=f"Milvus collection name (default: {DEFAULT_COLLECTION_NAME})",
    )
    parser.add_argument(
        "--milvus-host", default=os.environ.get("MILVUS_HOST", "localhost"),
    )
    parser.add_argument(
        "--milvus-port", type=int, default=int(os.environ.get("MILVUS_PORT", "19530")),
    )
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load and clean data but skip all writes",
    )
    parser.add_argument(
        "--skip-pgvector", action="store_true", default=True,
        help="Skip pgvector writes (default: True — Milvus only)",
    )
    parser.add_argument(
        "--no-skip-pgvector", dest="skip_pgvector", action="store_false",
        help="Enable pgvector writes",
    )
    parser.add_argument("--top-k-pg", type=int, default=5000)
    parser.add_argument(
        "--kb-ingest-url",
        default=os.environ.get("KB_INGEST_URL", "http://localhost:8000"),
    )
    return parser.parse_args()


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    sys.path.insert(0, str(PROJECT_ROOT))

    args = parse_args()

    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    embedding_base_url = os.environ.get("EMBEDDING_BASE_URL")
    embedding_dimension = int(os.environ.get("EMBEDDING_DIMENSION", str(EMBEDDING_DIMENSION_DEFAULT)))

    ingest(
        source=args.source,
        milvus_host=args.milvus_host,
        milvus_port=args.milvus_port,
        collection_name=args.milvus_collection,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        skip_pgvector=args.skip_pgvector,
        top_k_pg=args.top_k_pg,
        kb_ingest_url=args.kb_ingest_url,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_dimension=embedding_dimension,
        n_samples=args.n_samples,
    )


if __name__ == "__main__":
    main()
