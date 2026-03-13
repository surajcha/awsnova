"""Embedding and deduplication service using FAISS + Nova/Titan embeddings."""

from __future__ import annotations

import logging
from collections import defaultdict

import faiss
import numpy as np

from models.schemas import ExtractedEntity, ExtractionResult
from utils.bedrock_client import get_text_embedding

logger = logging.getLogger(__name__)


class EmbeddingIndex:
    """In-memory FAISS index for entity deduplication and similarity search."""

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # inner-product for cosine (normalized vecs)
        self.id_map: list[str] = []  # index position -> entity label
        self.embeddings: dict[str, np.ndarray] = {}

    def add_entity(self, label: str, embedding: list[float]):
        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)
        self.index.add(vec)
        self.id_map.append(label)
        self.embeddings[label] = vec[0]

    def find_similar(self, embedding: list[float], threshold: float = 0.85, top_k: int = 5) -> list[tuple[str, float]]:
        """Return [(label, similarity)] for matches above threshold."""
        if self.index.ntotal == 0:
            return []

        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)
        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            if dist >= threshold:
                results.append((self.id_map[idx], float(dist)))
        return results

    def reset(self):
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_map.clear()
        self.embeddings.clear()


# Singleton index
_entity_index = EmbeddingIndex()


def get_entity_index() -> EmbeddingIndex:
    return _entity_index


def embed_entity(label: str) -> list[float]:
    """Get embedding for an entity label."""
    return get_text_embedding(label)


def deduplicate_entities(
    extraction_results: list[ExtractionResult],
    threshold: float = 0.85,
) -> tuple[dict[str, str], list[ExtractedEntity]]:
    """Deduplicate entities across all extraction results.

    Returns:
        merge_map: {original_label -> canonical_label}
        unique_entities: deduplicated entity list
    """
    idx = get_entity_index()
    idx.reset()

    merge_map: dict[str, str] = {}
    unique_entities: list[ExtractedEntity] = []
    seen_labels: dict[str, ExtractedEntity] = {}

    # Collect all entities
    all_entities: list[ExtractedEntity] = []
    for result in extraction_results:
        all_entities.extend(result.entities)

    for entity in all_entities:
        label = entity.label.strip()
        if not label:
            continue

        # Check if we already have this exact label
        if label in seen_labels:
            merge_map[label] = label
            continue

        # Get embedding and check similarity
        try:
            emb = embed_entity(label)
        except Exception as exc:
            logger.warning("Embedding failed for '%s': %s", label, exc)
            seen_labels[label] = entity
            unique_entities.append(entity)
            merge_map[label] = label
            continue

        similar = idx.find_similar(emb, threshold=threshold)

        if similar:
            canonical = similar[0][0]
            merge_map[label] = canonical
            # Add alias
            if canonical in seen_labels:
                if label not in seen_labels[canonical].aliases:
                    seen_labels[canonical].aliases.append(label)
            logger.info("Merged '%s' -> '%s' (similarity=%.3f)", label, canonical, similar[0][1])
        else:
            # New unique entity
            idx.add_entity(label, emb)
            seen_labels[label] = entity
            unique_entities.append(entity)
            merge_map[label] = label

    logger.info(
        "Deduplication: %d total -> %d unique entities",
        len(all_entities),
        len(unique_entities),
    )
    return merge_map, unique_entities


def embed_fact(subject: str, predicate: str, obj: str) -> list[float]:
    """Get embedding for a fact triple (for fact-level dedup)."""
    fact_text = f"{subject} {predicate} {obj}"
    return get_text_embedding(fact_text)
