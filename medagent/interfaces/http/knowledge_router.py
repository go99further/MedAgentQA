"""
Knowledge base and Neo4j QA API endpoints.
"""

from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# Medical document models ---------------------------------------------------------
class MedicalDocModel(BaseModel):
    """Medical document payload stored in the vector knowledge base."""

    id: Optional[str] = Field(None, description="Document identifier")
    question: str = Field(..., description="Medical question")
    answer: str = Field(..., description="Medical answer")
    category: Optional[str] = Field(None, description="Medical category")
    source: Optional[str] = Field(None, description="Data source")


class SearchRequest(BaseModel):
    """Vector store search request."""

    query: str = Field(..., description="Query text")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of results to return")


class SearchResponse(BaseModel):
    """Vector store search response."""

    results: List[Dict[str, Any]] = Field(..., description="Matched documents")
    count: int = Field(..., description="Result count")


class GraphResponse(BaseModel):
    """Neo4j graph payload."""

    nodes: List[Dict[str, Any]] = Field(..., description="List of nodes")
    relationships: List[Dict[str, Any]] = Field(..., description="List of relationships")


class QARequest(BaseModel):
    """Neo4j QA request."""

    query: str = Field(..., description="User question")
    include_graph: bool = Field(False, description="Return the cached graph in the response")
    refresh_graph: bool = Field(False, description="Refresh the cached graph before returning it")


class QAResponse(BaseModel):
    """Neo4j QA response."""

    answer: str = Field(..., description="Natural language answer")
    question_type: str = Field(..., description="Detected question type")
    cypher: List[str] = Field(..., description="Generated Cypher queries")
    graph: Optional[GraphResponse] = Field(None, description="Optional graph data")


# Dependency helpers ----------------------------------------------------------
def get_knowledge_service():
    """Return the vector knowledge base service."""
    from medagent.infrastructure.knowledge import KnowledgeService

    return KnowledgeService()


# Vector store CRUD -----------------------------------------------------------
@router.post("/documents", status_code=201)
async def add_medical_document(
    doc: MedicalDocModel,
    service=Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Add a single medical document to the vector knowledge base."""
    try:
        if not doc.id:
            import uuid

            doc.id = f"doc_{uuid.uuid4().hex[:8]}"

        success = await service.add_document(doc_id=doc.id, doc_data=doc.dict())
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add document")

        return {"status": "success", "message": "Document added", "doc_id": doc.id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error adding document: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/documents/batch", status_code=201)
async def add_documents_batch(
    docs: List[MedicalDocModel],
    service=Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Add medical documents in batch."""
    try:
        import uuid

        for doc in docs:
            if not doc.id:
                doc.id = f"doc_{uuid.uuid4().hex[:8]}"

        result = await service.add_documents_batch([doc.dict() for doc in docs])
        return {
            "status": "success",
            "message": f"Inserted {result['success']} documents",
            "statistics": result,
        }
    except Exception as exc:
        logger.error(f"Error in batch add: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    service=Depends(get_knowledge_service),
) -> SearchResponse:
    """Search the vector knowledge base."""
    try:
        results = await service.search(query=request.query, top_k=request.top_k)
        return SearchResponse(results=results, count=len(results))
    except Exception as exc:
        logger.error(f"Search error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    service=Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Delete a medical document."""
    try:
        success = await service.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or deletion failed")

        return {"status": "success", "message": f"Document {doc_id} deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Delete error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats")
async def get_stats(
    service=Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Return vector store statistics."""
    try:
        stats = await service.get_stats()
        return {"status": "success", "data": stats}
    except Exception as exc:
        logger.error(f"Stats error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/clear")
async def clear_knowledge_base(
    confirm: bool = False,
    service=Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Clear the vector store (dangerous operation)."""
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required to clear the store")

    try:
        success = await service.clear()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to clear the store")
        return {"status": "success", "message": "Knowledge base cleared"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Clear error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
