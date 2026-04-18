"""Knowledge base service implemented with LangChain primitives."""

import asyncio
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from medagent.config import settings
from .embeddings import OpenAICompatibleEmbeddings
from .vector_store import VectorStore
from .reranker import Reranker


class KnowledgeService:
    """Facade for ingesting documents and performing similarity search."""

    def __init__(
        self,
        *,
        vector_store: Optional[VectorStore] = None,
        collection_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.KB_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.KB_CHUNK_OVERLAP

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", " "],
            length_function=len,  # 使用字符长度而不是 tiktoken
        )

        embedding_api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
        self.embedder = OpenAICompatibleEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=embedding_api_key,
            base_url=settings.EMBEDDING_BASE_URL,
            dimension=settings.EMBEDDING_DIMENSION,
        )

        self.vector_store = vector_store or VectorStore(
            collection_name=collection_name or settings.MILVUS_COLLECTION,
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
            dimension=settings.EMBEDDING_DIMENSION,
            index_type=settings.MILVUS_INDEX_TYPE,
            metric_type=settings.MILVUS_METRIC_TYPE,
        )

        self.reranker = Reranker()

        logger.info(
            "KnowledgeService initialised (chunk_size=%s, chunk_overlap=%s)",
            self.chunk_size,
            self.chunk_overlap,
        )

    async def ingest_text(
        self,
        text: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not text or not text.strip():
            return {"add_count": 0, "ids": []}

        documents = await asyncio.to_thread(self._split_into_documents, text, metadata or {})
        if not documents:
            return {"add_count": 0, "ids": []}

        embeddings = await asyncio.to_thread(
            self.embedder.embed_documents,
            [doc.page_content for doc in documents],
        )

        result = await asyncio.to_thread(self._store_documents, documents, embeddings)
        return result

    async def add_document(
        self,
        *,
        doc_id: Optional[str],
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        meta = metadata.copy() if metadata else {}
        meta.setdefault("title", title)
        meta.setdefault("name", title)
        if doc_id:
            meta.setdefault("document_id", doc_id)
        result = await self.ingest_text(content, metadata=meta)
        return result.get("add_count", 0) > 0

    async def add_medical_document(self, condition_id: str, doc_data: Dict[str, Any]) -> bool:
        document = self._format_medical_document(doc_data)
        metadata = {
            "condition_id": condition_id,
            "name": doc_data.get("name", ""),
            "department": doc_data.get("department", ""),
            "severity": doc_data.get("severity", ""),
        }
        result = await self.ingest_text(document, metadata=metadata)
        return result.get("add_count", 0) > 0

    async def add_medical_documents_batch(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        success_count = 0
        error_count = 0
        for doc in documents:
            condition_id = doc.get("id") or doc.get("condition_id") or str(uuid4())
            if await self.add_medical_document(condition_id, doc):
                success_count += 1
            else:
                error_count += 1
        return {"success": success_count, "error": error_count, "total": len(documents)}

    async def search(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filter_expr: Optional[str] = None,
        filter_by_similarity: bool = True,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        top_k = top_k or settings.KB_TOP_K
        similarity_threshold = (
            similarity_threshold if similarity_threshold is not None else settings.KB_SIMILARITY_THRESHOLD
        )

        # 如果启用 reranker，先召回更多候选文档
        recall_k = top_k
        if self.reranker.enabled:
            recall_k = settings.RERANK_MAX_CANDIDATES  # 召回更多文档用于重排

        embedding = await asyncio.to_thread(self.embedder.embed_query, query)
        results = await asyncio.to_thread(
            self.vector_store.search,
            embedding,
            recall_k,  # 使用更大的召回数量
            filter_expr,
        )

        candidates = results
        if filter_by_similarity and similarity_threshold is not None:
            candidates = [r for r in candidates if r.get("score", 0.0) >= similarity_threshold]

        # 使用 reranker 精排
        if candidates and self.reranker.enabled:
            candidates = await self.reranker.rerank(query, candidates, top_k)

        if self.reranker.enabled:
            candidates = [
                r
                for r in candidates
                if r.get("rerank_score", 0.0) >= settings.KB_RERANK_SCORE_THRESHOLD
            ]
        elif not filter_by_similarity and similarity_threshold is not None:
            candidates = [r for r in candidates if r.get("score", 0.0) >= similarity_threshold]

        return candidates[:top_k]

    async def delete_document(self, document_id: str) -> bool:
        return await asyncio.to_thread(self.vector_store.delete_documents, [document_id])

    async def get_stats(self) -> Dict[str, Any]:
        def _stats() -> Dict[str, Any]:
            stats = self.vector_store.get_collection_stats()
            stats.update(
                {
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "embedding_model": settings.EMBEDDING_MODEL,
                }
            )
            return stats

        return await asyncio.to_thread(_stats)

    async def clear(self) -> bool:
        return await asyncio.to_thread(self.vector_store.clear_collection)

    async def close(self) -> None:
        await asyncio.to_thread(self.vector_store.close)

    def _split_into_documents(self, text: str, metadata: Dict[str, Any]) -> List[Document]:
        base_document = Document(page_content=text, metadata=metadata)
        chunks = self.splitter.split_documents([base_document])
        return chunks or [base_document]

    def _store_documents(
        self,
        documents: List[Document],
        embeddings: List[List[float]],
    ) -> Dict[str, Any]:
        if not documents or not embeddings:
            return {"add_count": 0, "ids": [], "stored": False}

        ids: List[str] = []
        contents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for index, doc in enumerate(documents):
            metadata = dict(doc.metadata or {})
            base_id = metadata.get("document_id") or metadata.get("id") or metadata.get("source") or uuid4().hex
            chunk_id = f"{base_id}_{index}"
            metadata.setdefault("document_id", base_id)
            metadata.setdefault("chunk_id", chunk_id)
            metadata.setdefault("name", metadata.get("name") or metadata.get("title") or "")

            ids.append(chunk_id)
            contents.append(doc.page_content)
            metadatas.append(metadata)

        success = self.vector_store.add_documents(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
        )

        return {"add_count": len(ids) if success else 0, "ids": ids, "stored": success}

    @staticmethod
    def _format_medical_document(doc_data: Dict[str, Any]) -> str:
        parts: List[str] = []
        name = doc_data.get("name")
        if name:
            parts.append(f"病症名称：{name}")

        department = doc_data.get("department")
        if department:
            parts.append(f"所属科室：{department}")

        severity = doc_data.get("severity")
        if severity:
            parts.append(f"严重程度：{severity}")

        cause = doc_data.get("cause") or doc_data.get("etiology")
        if cause:
            parts.append(f"病因：{cause}")

        symptoms = doc_data.get("symptoms") or doc_data.get("symptom_list")
        if symptoms:
            if isinstance(symptoms, list):
                formatted = "、".join(str(item) for item in symptoms)
            else:
                formatted = str(symptoms)
            parts.append(f"症状：{formatted}")

        treatments = doc_data.get("treatments")
        if treatments:
            if isinstance(treatments, list):
                treatment_lines = [f"方案{idx + 1}：{t}" for idx, t in enumerate(treatments)]
                parts.extend(treatment_lines)
            else:
                parts.append(f"治疗方案：{treatments}")

        medications = doc_data.get("medications")
        if medications:
            if isinstance(medications, list):
                formatted = "、".join(str(item) for item in medications)
            else:
                formatted = str(medications)
            parts.append(f"常用药物：{formatted}")

        precautions = doc_data.get("precautions")
        if precautions:
            parts.append(f"注意事项：{precautions}")

        prognosis = doc_data.get("prognosis")
        if prognosis:
            parts.append(f"预后：{prognosis}")

        return "\n".join(parts)
