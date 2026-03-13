"""Entity & relation extraction service using Amazon Nova via Bedrock."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from models.schemas import ExtractionResult, ExtractedEntity, ExtractedRelation, TextChunk
from utils.bedrock_client import invoke_nova_text, invoke_nova_multimodal

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge-graph extraction engine.
Given a text chunk (and optionally an image), extract all entities and relationships.

Entity types to detect: System, Service, Process, Team, Policy, KPI, Database, API, Component, Organization, Person, Technology.

Relationship types to detect: depends_on, part_of, owned_by, applies_to, connects_to, manages, uses, provides, consumes, deployed_on, communicates_with.

Return ONLY valid JSON in this exact format:
{
  "entities": [
    {"label": "...", "type": "...", "aliases": [], "confidence": 0.95}
  ],
  "relations": [
    {"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9, "effective_from": null}
  ]
}

Rules:
- Extract ALL meaningful entities and relationships from the text.
- Use consistent naming — prefer the most specific label.
- Set confidence between 0.0 and 1.0 based on how explicit the information is.
- If a date/version context exists, set effective_from.
- Do NOT include explanation or markdown — only the JSON object."""

EXTRACTION_USER_PROMPT = """Extract entities and relationships from the following text chunk:

---
{text}
---

Source: {source_uri}, Page: {page}

Return the JSON extraction result."""


def extract_from_chunk(chunk: TextChunk) -> ExtractionResult:
    """Extract entities and relations from a single text chunk using Nova."""
    prompt = EXTRACTION_USER_PROMPT.format(
        text=chunk.text,
        source_uri=chunk.source_uri,
        page=chunk.page or "N/A",
    )

    try:
        raw = invoke_nova_text(prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT, max_tokens=2048)
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        entities = [ExtractedEntity(**e) for e in data.get("entities", [])]
        relations = [ExtractedRelation(**r) for r in data.get("relations", [])]

        return ExtractionResult(
            entities=entities,
            relations=relations,
            source_uri=chunk.source_uri,
            page=chunk.page,
            span=chunk.text[:100],
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Extraction parse error for chunk %s: %s", chunk.chunk_index, exc)
        return ExtractionResult(source_uri=chunk.source_uri, page=chunk.page)


def extract_from_image(image_path: str, source_uri: str) -> ExtractionResult:
    """Extract entities and relations from an image using Nova multimodal."""
    prompt = (
        "Extract all entities and relationships visible in this image. "
        "Return ONLY JSON in the format: "
        '{"entities": [{"label": "...", "type": "...", "aliases": [], "confidence": 0.9}], '
        '"relations": [{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9}]}'
    )

    try:
        raw = invoke_nova_multimodal(
            prompt=prompt,
            image_path=image_path,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            max_tokens=2048,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        entities = [ExtractedEntity(**e) for e in data.get("entities", [])]
        relations = [ExtractedRelation(**r) for r in data.get("relations", [])]

        return ExtractionResult(
            entities=entities,
            relations=relations,
            source_uri=source_uri,
            page=None,
            span=f"[image: {Path(image_path).name}]",
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Image extraction error for %s: %s", image_path, exc)
        return ExtractionResult(source_uri=source_uri)


def extract_from_chunks(chunks: list[TextChunk]) -> list[ExtractionResult]:
    """Run extraction on all text chunks."""
    results = []
    for chunk in chunks:
        result = extract_from_chunk(chunk)
        if result.entities or result.relations:
            results.append(result)
    return results
