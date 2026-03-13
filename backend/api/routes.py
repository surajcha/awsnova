"""FastAPI API routes matching the MVP spec."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from config import settings
from models.schemas import (
    BuildGraphRequest,
    BuildGraphResponse,
    QueryResponse,
    UploadResponse,
)
from services.graph_service import build_graph, get_knowledge_graph
from services.query_service import query_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory document registry (doc_id -> metadata)
_documents: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".tiff", ".bmp"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a document (PDF, image, or text file).

    POST /api/upload
    Form-data: file
    Returns: { doc_id, name, pages, status }
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f}MB). Max: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    doc_id = str(uuid.uuid4())[:12]
    safe_name = f"{doc_id}_{file.filename}"
    file_path = Path(settings.UPLOAD_DIR) / safe_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Estimate page count (actual count determined during build)
    pages = 0
    if ext == ".pdf":
        from PyPDF2 import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(content))
        pages = len(reader.pages)

    _documents[doc_id] = {
        "path": str(file_path),
        "name": file.filename,
        "pages": pages,
    }

    logger.info("Uploaded %s as doc_id=%s (%d pages)", file.filename, doc_id, pages)

    return UploadResponse(
        doc_id=doc_id,
        name=file.filename,
        pages=pages,
        status="uploaded",
    )


@router.post("/build-graph", response_model=BuildGraphResponse)
async def build_graph_endpoint(request: BuildGraphRequest):
    """Build knowledge graph from uploaded documents.

    POST /api/build-graph
    Body: { "doc_ids": ["..."] }
    Returns: { nodes, edges, summary }
    """
    if not request.doc_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    # Validate doc IDs
    missing = [d for d in request.doc_ids if d not in _documents]
    if missing:
        raise HTTPException(status_code=404, detail=f"Documents not found: {missing}")

    try:
        nodes, edges, summary = build_graph(request.doc_ids, _documents)
        return BuildGraphResponse(nodes=nodes, edges=edges, summary=summary)
    except Exception as exc:
        logger.exception("Graph build failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/query", response_model=QueryResponse)
async def query_endpoint(q: str = Query(..., description="Natural language question")):
    """Query the knowledge graph with natural language.

    GET /api/query?q=...
    Returns: { answer, items: [{ subject, predicate, object, citations }] }
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        return query_graph(q)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/graph/stats")
async def graph_stats():
    """Get current graph statistics."""
    kg = get_knowledge_graph()
    return {
        "node_count": len(kg.nodes),
        "edge_count": len(kg.edges),
        "document_count": len(kg.documents),
        "summary": kg.summary(),
    }


@router.get("/graph/nodes")
async def get_graph_nodes():
    """Get all nodes in the graph."""
    kg = get_knowledge_graph()
    return list(kg.nodes.values())


@router.get("/graph/edges")
async def get_graph_edges():
    """Get all edges in the graph."""
    kg = get_knowledge_graph()
    return list(kg.edges.values())


@router.get("/documents")
async def list_documents():
    """List all uploaded documents."""
    return [
        {"doc_id": doc_id, **info}
        for doc_id, info in _documents.items()
    ]


@router.delete("/graph/reset")
async def reset_graph():
    """Reset the knowledge graph (clear all nodes/edges)."""
    kg = get_knowledge_graph()
    kg.reset()
    return {"status": "Graph reset successfully"}
