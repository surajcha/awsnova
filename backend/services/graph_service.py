"""Knowledge graph construction and management using NetworkX."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import networkx as nx

from models.schemas import (
    DocumentRecord,
    ExtractionResult,
    GraphEdge,
    GraphNode,
    NodeStatus,
    NodeType,
    Provenance,
    TextChunk,
)
from services.ocr_service import extract_content
from services.chunking_service import chunk_document_pages
from services.extraction_service import extract_from_chunks, extract_from_image
from services.embedding_service import deduplicate_entities

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """In-memory knowledge graph backed by NetworkX."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.documents: dict[str, DocumentRecord] = {}
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
        self.graph.add_node(
            node.id,
            type=node.type.value,
            label=node.label,
            aliases=node.aliases,
            confidence=node.confidence,
            status=node.status.value,
        )

    def add_edge(self, edge: GraphEdge):
        self.edges[edge.id] = edge
        self.graph.add_edge(
            edge.subject_id,
            edge.object_id,
            id=edge.id,
            predicate=edge.predicate,
            confidence=edge.confidence,
            provenance=edge.provenance.model_dump(),
        )

    def get_node_by_label(self, label: str) -> GraphNode | None:
        for node in self.nodes.values():
            if node.label.lower() == label.lower():
                return node
            if label.lower() in [a.lower() for a in node.aliases]:
                return node
        return None

    def get_neighbors(self, node_id: str, direction: str = "both") -> list[dict]:
        """Get neighboring nodes and edges for a given node."""
        results = []
        if direction in ("out", "both"):
            for _, target, data in self.graph.out_edges(node_id, data=True):
                if target in self.nodes:
                    results.append({
                        "edge": data,
                        "node": self.nodes[target],
                        "direction": "outgoing",
                    })
        if direction in ("in", "both"):
            for source, _, data in self.graph.in_edges(node_id, data=True):
                if source in self.nodes:
                    results.append({
                        "edge": data,
                        "node": self.nodes[source],
                        "direction": "incoming",
                    })
        return results

    def get_subgraph(self, node_ids: list[str], depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Get a subgraph around the given node IDs up to a certain depth."""
        visited = set(node_ids)
        frontier = set(node_ids)

        for _ in range(depth):
            new_frontier = set()
            for nid in frontier:
                for neighbor in self.graph.successors(nid):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_frontier.add(neighbor)
                for neighbor in self.graph.predecessors(nid):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_frontier.add(neighbor)
            frontier = new_frontier

        sub_nodes = [self.nodes[nid] for nid in visited if nid in self.nodes]
        sub_edges = [
            edge for edge in self.edges.values()
            if edge.subject_id in visited and edge.object_id in visited
        ]
        return sub_nodes, sub_edges

    def get_facts_text(self, node_ids: list[str] | None = None) -> str:
        """Return a textual summary of facts for reasoning."""
        lines = []
        edges_to_show = self.edges.values()
        if node_ids:
            node_set = set(node_ids)
            edges_to_show = [
                e for e in self.edges.values()
                if e.subject_id in node_set or e.object_id in node_set
            ]

        for edge in edges_to_show:
            subj = self.nodes.get(edge.subject_id)
            obj = self.nodes.get(edge.object_id)
            if subj and obj:
                cite = ""
                if edge.provenance.source_uri:
                    cite = f" [source: {edge.provenance.source_uri}"
                    if edge.provenance.page:
                        cite += f", page {edge.provenance.page}"
                    cite += "]"
                lines.append(
                    f"- {subj.label} --[{edge.predicate}]--> {obj.label} "
                    f"(confidence: {edge.confidence}){cite}"
                )
        return "\n".join(lines)

    def summary(self) -> str:
        return (
            f"{len(self.nodes)} nodes, {len(self.edges)} edges, "
            f"{len(self.documents)} documents ingested"
        )

    def reset(self):
        self.graph.clear()
        self.nodes.clear()
        self.edges.clear()
        self.documents.clear()


# Singleton
_kg = KnowledgeGraph()


def get_knowledge_graph() -> KnowledgeGraph:
    return _kg


def _make_node_id(label: str) -> str:
    """Create a deterministic node ID from a label."""
    return label.lower().replace(" ", "_").replace("-", "_")


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def build_graph(doc_ids: list[str], documents: dict[str, dict]) -> tuple[list[GraphNode], list[GraphEdge], str]:
    """Full pipeline: OCR -> chunk -> extract -> embed/dedup -> build graph.

    Args:
        doc_ids: list of document IDs to process
        documents: dict mapping doc_id -> {"path": str, "name": str, "pages": int}

    Returns:
        (nodes, edges, summary_text)
    """
    kg = get_knowledge_graph()
    all_chunks: list[TextChunk] = []
    all_extractions: list[ExtractionResult] = []

    for doc_id in doc_ids:
        doc_info = documents.get(doc_id)
        if not doc_info:
            logger.warning("Document %s not found", doc_id)
            continue

        file_path = doc_info["path"]
        ext = Path(file_path).suffix.lower()

        # Register document
        doc_record = DocumentRecord(
            id=doc_id,
            name=doc_info["name"],
            uri=file_path,
            pages=doc_info.get("pages", 0),
        )
        kg.documents[doc_id] = doc_record

        if ext in IMAGE_EXTENSIONS:
            # Multimodal extraction directly on image
            result = extract_from_image(file_path, source_uri=file_path)
            if result.entities or result.relations:
                all_extractions.append(result)
        else:
            # Text-based: OCR -> chunk -> extract
            pages = extract_content(file_path)
            doc_info["pages"] = len(pages)
            doc_record.pages = len(pages)

            chunks = chunk_document_pages(pages, source_uri=file_path)
            all_chunks.extend(chunks)

    # Extract entities/relations from text chunks
    if all_chunks:
        text_extractions = extract_from_chunks(all_chunks)
        all_extractions.extend(text_extractions)

    if not all_extractions:
        return [], [], "No entities or relations extracted."

    # Deduplicate entities using embeddings
    merge_map, unique_entities = deduplicate_entities(all_extractions)

    # Build nodes
    for entity in unique_entities:
        node_id = _make_node_id(entity.label)
        node = GraphNode(
            id=node_id,
            type=NodeType.ENTITY,
            label=entity.label,
            aliases=entity.aliases,
            confidence=entity.confidence,
            properties={"entity_type": entity.type},
        )
        kg.add_node(node)

    # Build edges
    for extraction in all_extractions:
        for rel in extraction.relations:
            # Resolve merged labels
            subj_label = merge_map.get(rel.subject, rel.subject)
            obj_label = merge_map.get(rel.object, rel.object)

            subj_id = _make_node_id(subj_label)
            obj_id = _make_node_id(obj_label)

            # Ensure both nodes exist
            if subj_id not in kg.nodes:
                kg.add_node(GraphNode(
                    id=subj_id, label=subj_label, confidence=0.7,
                    properties={"entity_type": "Unknown"},
                ))
            if obj_id not in kg.nodes:
                kg.add_node(GraphNode(
                    id=obj_id, label=obj_label, confidence=0.7,
                    properties={"entity_type": "Unknown"},
                ))

            edge_id = str(uuid.uuid4())[:8]
            edge = GraphEdge(
                id=edge_id,
                subject_id=subj_id,
                predicate=rel.predicate,
                object_id=obj_id,
                provenance=Provenance(
                    source_uri=extraction.source_uri,
                    page=extraction.page,
                    span=extraction.span,
                ),
                effective_from=rel.effective_from,
                confidence=rel.confidence,
            )
            kg.add_edge(edge)

    summary = (
        f"Graph built: {len(kg.nodes)} entities, {len(kg.edges)} relations "
        f"from {len(doc_ids)} document(s)."
    )
    logger.info(summary)

    return list(kg.nodes.values()), list(kg.edges.values()), summary
