from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# --- Enums ---

class NodeType(str, Enum):
    ENTITY = "Entity"
    DOCUMENT = "Document"
    CONCEPT = "Concept"


class NodeStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


# --- Provenance ---

class Provenance(BaseModel):
    source_uri: str
    page: int | None = None
    span: str | None = None


# --- Graph Node ---

class GraphNode(BaseModel):
    id: str
    type: NodeType = NodeType.ENTITY
    label: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    status: NodeStatus = NodeStatus.ACTIVE
    properties: dict = Field(default_factory=dict)


# --- Graph Edge ---

class GraphEdge(BaseModel):
    id: str
    subject_id: str
    predicate: str
    object_id: str
    provenance: Provenance
    effective_from: str | None = None
    confidence: float = 1.0


# --- Document ---

class DocumentRecord(BaseModel):
    id: str
    name: str
    uri: str
    pages: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    content_type: str = "application/pdf"


# --- Extraction Results ---

class ExtractedEntity(BaseModel):
    label: str
    type: str  # System, Service, Process, Team, Policy, KPI, etc.
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class ExtractedRelation(BaseModel):
    subject: str
    predicate: str  # depends_on, part_of, owned_by, applies_to, etc.
    object: str
    confidence: float = 1.0
    effective_from: str | None = None


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
    source_uri: str = ""
    page: int | None = None
    span: str | None = None


# --- API Request/Response ---

class UploadResponse(BaseModel):
    doc_id: str
    name: str
    pages: int
    status: str = "uploaded"


class BuildGraphRequest(BaseModel):
    doc_ids: list[str]


class BuildGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: str


class QueryResponse(BaseModel):
    answer: str
    items: list[QueryItem] = Field(default_factory=list)


class QueryItem(BaseModel):
    subject: str
    predicate: str
    object: str
    citations: list[Provenance] = Field(default_factory=list)


# --- Chunk ---

class TextChunk(BaseModel):
    text: str
    source_uri: str
    page: int | None = None
    chunk_index: int = 0
