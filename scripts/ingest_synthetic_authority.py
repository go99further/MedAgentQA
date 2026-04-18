"""
ingest_synthetic_authority.py
==============================
将 data/medical_kg/synthetic_authority_qa.jsonl 导入 Milvus v9c_authority collection。

所有 chunk 的 evidence_level 硬编码为 "A"（来源已保证 >=200 字）。

Usage::
    python scripts/ingest_synthetic_authority.py [--drop-existing] [--dry-run]
"""
import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("ingest_synthetic_authority")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "medical_kg" / "synthetic_authority_qa.jsonl"
DEFAULT_COLLECTION = "v9c_authority"
EMBEDDING_DIMENSION_DEFAULT = 1536
MAX_RETRIES = 3
BACKOFF_BASE = 2.0

CHINESE_SEPARATORS = ["\n\n", "\n", "\u3002", "\uff01", "\uff1f", "\uff1b", "\uff0c", "\u3001", " ", ""]


class EmbeddingClient:
    def __init__(self, *, model: str, api_key: Optional[str], base_url: Optional[str],
                 dimension: int = EMBEDDING_DIMENSION_DEFAULT, max_batch_size: int = 25):
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
                logger.warning("Embedding failed (attempt %d/%d): %s -- retry in %.1fs", attempt, MAX_RETRIES, exc, wait)
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
            FieldSchema("question_id", DataType.VARCHAR, max_length=256),
            FieldSchema("ans_id", DataType.VARCHAR, max_length=64),
            FieldSchema("department", DataType.VARCHAR, max_length=128),
            FieldSchema("evidence_level", DataType.VARCHAR, max_length=8),
        ]
        schema = CollectionSchema(fields, description="Synthetic authority QA from Neo4j schema (v9c_authority)")
        col = Collection(name=name, schema=schema)
        col.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}})
        logger.info("Created collection '%s' (dim=%d)", name, dimension)
    col.load()
    return col


def _chunk_id(disease: str, qa_type: str, chunk_idx: int) -> str:
    raw = f"v9c-{disease}-{qa_type}-c{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:24]


def ingest(*, input_path: Path, milvus_host: str, milvus_port: int,
           collection_name: str, batch_size: int, dry_run: bool,
           embedding_model: str, embedding_api_key: Optional[str],
           embedding_base_url: Optional[str], embedding_dimension: int,
           drop_existing: bool = False) -> Dict[str, Any]:
    import json
    t0 = time.time()
    stats = {"total_rows": 0, "total_chunks": 0, "milvus_inserted": 0, "embed_errors": 0, "elapsed_seconds": 0.0}

    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    stats["total_rows"] = len(records)
    logger.info("Loaded %d QA records from %s", len(records), input_path)

    if dry_run:
        logger.info("[DRY RUN] First 3 records:")
        for r in records[:3]:
            logger.info("  [%s] %s: Q=%s... A_len=%d level=%s",
                        r["qa_type"], r["disease"], r["question"][:50], len(r["answer"]), r["evidence_level"])
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

    for record in tqdm(records, desc="Ingesting authority QA"):
        chunks = splitter.split_text(record["answer"])
        if not chunks:
            continue
        try:
            vectors = embed_client.embed_batch(chunks)
        except Exception as exc:
            logger.warning("Embedding failed for %s/%s: %s", record["disease"], record["qa_type"], exc)
            stats["embed_errors"] += 1
            continue
        for ci, (chunk, vec) in enumerate(zip(chunks, vectors)):
            ids_buf.append(_chunk_id(record["disease"], record["qa_type"], ci))
            emb_buf.append(vec)
            content_buf.append(chunk[:65535])
            qid_buf.append(record["disease"][:256])
            aid_buf.append(record["qa_type"][:64])
            dept_buf.append(record.get("department", "")[:128])
            evidence_level_buf.append("A")  # all synthetic authority chunks are A-level
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

    parser = argparse.ArgumentParser(description="Ingest synthetic authority QA into v9c_authority Milvus collection.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--milvus-collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--milvus-host", default=os.environ.get("MILVUS_HOST", "localhost"))
    parser.add_argument("--milvus-port", type=int, default=int(os.environ.get("MILVUS_PORT", "19530")))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--drop-existing", action="store_true",
                        help="Drop and recreate the Milvus collection.")
    args = parser.parse_args()

    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    embedding_base_url = os.environ.get("EMBEDDING_BASE_URL")
    embedding_dimension = int(os.environ.get("EMBEDDING_DIMENSION", str(EMBEDDING_DIMENSION_DEFAULT)))

    stats = ingest(
        input_path=Path(args.input),
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
    print(f"Ingestion complete: {stats}")


if __name__ == "__main__":
    main()
