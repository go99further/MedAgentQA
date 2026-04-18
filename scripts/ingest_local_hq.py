"""
ingest_local_hq.py
==================
从本地 cMedQA2 CSV 构建高质量子集，导入 Milvus chimedqa2 collection。

用途：当 HuggingFace 不可访问时，用本地数据模拟"高质量知识库"实验。

质量过滤策略（vs cmedqa2 默认导入）：
  - 答案长度 >= 100 字符（过滤掉过短的低质量回答）
  - 答案长度 <= 249 字符（cMedQA2 实际上限）
  - 非纯数字答案
  - 按答案长度降序取 top-N（最详细的回答优先）

Usage::
    python scripts/ingest_local_hq.py --n-samples 5000
    python scripts/ingest_local_hq.py --n-samples 5000 --dry-run
"""
import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("ingest_local_hq")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_CSV = PROJECT_ROOT / "data" / "cmedqa2" / "answer.csv"
QUESTION_CSV = PROJECT_ROOT / "data" / "cmedqa2" / "question.csv"

DEFAULT_COLLECTION = "chimedqa2"
EMBEDDING_DIMENSION_DEFAULT = 1536
MIN_ANSWER_LEN = 100
MAX_RETRIES = 3
BACKOFF_BASE = 2.0

CHINESE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]


def load_hq_data(n_samples: Optional[int] = None) -> pd.DataFrame:
    logger.info("Loading local cMedQA2 data...")
    df_a = pd.read_csv(ANSWER_CSV, encoding="utf-8")
    df_q = pd.read_csv(QUESTION_CSV, encoding="utf-8")

    merged = df_q.merge(df_a, on="question_id", how="inner")
    merged = merged.rename(columns={"content_x": "question", "content_y": "answer"})
    merged = merged[["question_id", "ans_id", "question", "answer"]].copy()
    merged["question"] = merged["question"].fillna("").astype(str)
    merged["answer"] = merged["answer"].fillna("").astype(str)

    before = len(merged)
    merged = merged[merged["answer"].str.strip().str.len() >= MIN_ANSWER_LEN]
    merged = merged[~merged["answer"].str.strip().str.match(r"^\d+$")]
    merged["ans_len"] = merged["answer"].str.len()
    merged = merged.sort_values("ans_len", ascending=False)
    after = len(merged)
    logger.info("Quality filter: %d → %d rows (kept top %d by length)", before, after, after)

    if n_samples:
        merged = merged.head(n_samples)

    logger.info("Using %d rows for ingestion", len(merged))
    return merged.reset_index(drop=True)


class EmbeddingClient:
    def __init__(self, *, model: str, api_key: Optional[str], base_url: Optional[str],
                 dimension: int = EMBEDDING_DIMENSION_DEFAULT, max_batch_size: int = 64):
        self.model = model
        self.dimension = dimension
        self.max_batch_size = max_batch_size
        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        logger.info("Embedding client: model=%s base_url=%s dim=%d", model, base_url or "openai", dimension)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        sanitised = [(t or "").strip() or " " for t in texts]
        all_vecs: List[List[float]] = []
        for start in range(0, len(sanitised), self.max_batch_size):
            batch = sanitised[start: start + self.max_batch_size]
            all_vecs.extend(self._call_with_retry(batch))
        return all_vecs

    def _call_with_retry(self, batch: List[str]) -> List[List[float]]:
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.embeddings.create(model=self.model, input=batch, timeout=120.0)
                return [list(item.embedding) for item in resp.data]
            except Exception as exc:
                last_exc = exc
                wait = BACKOFF_BASE ** attempt
                logger.warning("Embedding failed (attempt %d/%d): %s — retry in %.1fs", attempt, MAX_RETRIES, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"Embedding failed after {MAX_RETRIES} retries") from last_exc


def _ensure_collection(host: str, port: int, dimension: int, name: str, drop_existing: bool = False) -> Collection:
    connections.connect(alias="default", host=host, port=port)
    logger.info("Connected to Milvus %s:%d", host, port)
    if drop_existing and utility.has_collection(name):
        utility.drop_collection(name)
        logger.info("Dropped existing collection '%s' (--drop-existing)", name)
    if utility.has_collection(name):
        col = Collection(name)
        logger.info("Using existing collection '%s'", name)
    else:
        fields = [
            FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema("content", DataType.VARCHAR, max_length=65535),
            FieldSchema("question_id", DataType.VARCHAR, max_length=64),
            FieldSchema("ans_id", DataType.VARCHAR, max_length=64),
            FieldSchema("department", DataType.VARCHAR, max_length=128),
            FieldSchema("evidence_level", DataType.VARCHAR, max_length=8),
        ]
        schema = CollectionSchema(fields, description="cMedQA2 high-quality subset (chimedqa2)")
        col = Collection(name=name, schema=schema)
        col.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}})
        logger.info("Created collection '%s' (dim=%d)", name, dimension)
    col.load()
    return col


def _chunk_id(row_idx: int, chunk_idx: int) -> str:
    raw = f"chimedqa2-r{row_idx}-c{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:24]


def _compute_evidence_level(answer_text: str) -> str:
    """Assign evidence level based on answer length heuristic.

    A: detailed answer (≥150 chars) — high quality
    B: medium answer (50–149 chars) — medium quality
    C: short answer (<50 chars)     — low quality
    """
    n = len(answer_text.strip())
    if n >= 150:
        return "A"
    elif n >= 50:
        return "B"
    return "C"


def ingest(*, n_samples: Optional[int], milvus_host: str, milvus_port: int,
           collection_name: str, batch_size: int, dry_run: bool,
           embedding_model: str, embedding_api_key: Optional[str],
           embedding_base_url: Optional[str], embedding_dimension: int,
           drop_existing: bool = False) -> Dict[str, Any]:
    t0 = time.time()
    stats = {"total_rows": 0, "total_chunks": 0, "milvus_inserted": 0, "embed_errors": 0, "elapsed_seconds": 0.0}

    df = load_hq_data(n_samples)
    stats["total_rows"] = len(df)

    if dry_run:
        logger.info("[DRY RUN] First 3 rows:")
        for _, row in df.head(3).iterrows():
            logger.info("  Q: %s", row["question"][:80])
            logger.info("  A: %s", row["answer"][:120])
            logger.info("  len: %d", len(row["answer"]))
        logger.info("[DRY RUN] Stats: %s", stats)
        return stats

    embed_client = EmbeddingClient(
        model=embedding_model, api_key=embedding_api_key,
        base_url=embedding_base_url, dimension=embedding_dimension,
    )
    collection = _ensure_collection(milvus_host, milvus_port, embedding_dimension, collection_name, drop_existing=drop_existing)
    splitter = RecursiveCharacterTextSplitter(chunk_size=384, chunk_overlap=50, separators=CHINESE_SEPARATORS)

    ids_buf, emb_buf, content_buf, qid_buf, aid_buf, dept_buf, evidence_level_buf = [], [], [], [], [], [], []

    def _flush():
        if not ids_buf:
            return
        collection.insert([ids_buf, emb_buf, content_buf, qid_buf, aid_buf, dept_buf, evidence_level_buf])
        collection.flush()
        stats["milvus_inserted"] += len(ids_buf)
        ids_buf.clear(); emb_buf.clear(); content_buf.clear()
        qid_buf.clear(); aid_buf.clear(); dept_buf.clear(); evidence_level_buf.clear()

    for row_idx, row in tqdm(df.iterrows(), total=len(df), desc="Ingesting HQ"):
        chunks = splitter.split_text(row["answer"])
        if not chunks:
            continue
        try:
            vectors = embed_client.embed_batch(chunks)
        except Exception as exc:
            logger.warning("Embedding failed row %d: %s", row_idx, exc)
            stats["embed_errors"] += 1
            continue
        answer_level = _compute_evidence_level(row["answer"])
        for ci, (chunk, vec) in enumerate(zip(chunks, vectors)):
            ids_buf.append(_chunk_id(row_idx, ci))
            emb_buf.append(vec)
            content_buf.append(chunk[:65535])
            qid_buf.append(str(row["question_id"]))
            aid_buf.append(str(row["ans_id"]))
            dept_buf.append("")
            evidence_level_buf.append(answer_level)
            stats["total_chunks"] += 1
        if len(ids_buf) >= batch_size:
            _flush()

    _flush()
    stats["elapsed_seconds"] = round(time.time() - t0, 1)
    logger.info("Done: %s", stats)
    return stats


def main():
    from dotenv import load_dotenv
    load_dotenv(override=True)
    sys.path.insert(0, str(PROJECT_ROOT))

    parser = argparse.ArgumentParser(description="Ingest local cMedQA2 HQ subset into chimedqa2 collection.")
    parser.add_argument("--n-samples", type=int, default=5000)
    parser.add_argument("--milvus-collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--milvus-host", default=os.environ.get("MILVUS_HOST", "localhost"))
    parser.add_argument("--milvus-port", type=int, default=int(os.environ.get("MILVUS_PORT", "19530")))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--drop-existing", action="store_true",
                        help="Drop and recreate the Milvus collection (required when adding new schema fields).")
    args = parser.parse_args()

    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    embedding_base_url = os.environ.get("EMBEDDING_BASE_URL")
    embedding_dimension = int(os.environ.get("EMBEDDING_DIMENSION", str(EMBEDDING_DIMENSION_DEFAULT)))

    ingest(
        n_samples=args.n_samples,
        milvus_host=args.milvus_host,
        milvus_port=args.milvus_port,
        collection_name=args.milvus_collection,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_dimension=embedding_dimension,
        drop_existing=args.drop_existing,
    )


if __name__ == "__main__":
    main()
