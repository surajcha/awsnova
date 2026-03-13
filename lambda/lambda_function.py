"""
AWS Lambda function for Nova MKG — Multimodal Knowledge Graph Builder.

This Lambda handles all API endpoints:
  POST /list-documents  — List files in an S3 bucket
  POST /build-graph     — Download S3 files, extract entities via Bedrock, build graph
  POST /query           — Answer questions using the knowledge graph + Bedrock
  POST /graph-stats     — Get current graph statistics
  POST /reset           — Reset the in-memory graph

Deploy with a Lambda Function URL (or API Gateway).
Runtime: Python 3.11  |  Timeout: 900s  |  Memory: 2048-3072 MB
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import uuid
from pathlib import Path

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─── AWS Clients ──────────────────────────────────────────────────────────────

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
NOVA_TEXT_MODEL_ID = os.environ.get("NOVA_TEXT_MODEL_ID", "amazon.nova-pro-v1:0")
NOVA_LITE_MODEL_ID = os.environ.get("NOVA_LITE_MODEL_ID", "amazon.nova-lite-v1:0")
NOVA_EMBED_MODEL_ID = os.environ.get("NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.85"))

s3_client = boto3.client("s3", region_name=AWS_REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)


# ─── Bedrock Helpers ──────────────────────────────────────────────────────────

def invoke_nova_text(prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> str:
    """Invoke Nova Pro for text generation."""
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    system = [{"text": system_prompt}] if system_prompt else []

    body = {
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1, "topP": 0.9},
    }
    if system:
        body["system"] = system

    response = bedrock_runtime.invoke_model(
        modelId=NOVA_TEXT_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def invoke_nova_multimodal(prompt: str, image_bytes: bytes, image_format: str = "png",
                           system_prompt: str = "", max_tokens: int = 4096) -> str:
    """Invoke Nova Lite for multimodal (text + image) tasks."""
    content = [
        {"image": {"format": image_format, "source": {"bytes": base64.b64encode(image_bytes).decode("utf-8")}}},
        {"text": prompt},
    ]
    messages = [{"role": "user", "content": content}]
    system = [{"text": system_prompt}] if system_prompt else []

    body = {
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1, "topP": 0.9},
    }
    if system:
        body["system"] = system

    response = bedrock_runtime.invoke_model(
        modelId=NOVA_LITE_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def get_text_embedding(text: str) -> list[float]:
    """Generate text embedding using Titan Embed Text v2."""
    body = {"inputText": text[:8192], "dimensions": 1024, "normalize": True}
    response = bedrock_runtime.invoke_model(
        modelId=NOVA_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


# ─── Text Extraction (S3-based) ──────────────────────────────────────────────

def extract_text_from_s3(bucket: str, key: str) -> list[dict]:
    """Download file from S3 and extract text. Returns [{"page": int|None, "text": str}]."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()
    ext = Path(key).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(content, key)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return [{"page": None, "text": "", "image_bytes": content, "image_format": _get_image_format(ext)}]
    elif ext == ".txt":
        text = content.decode("utf-8", errors="ignore").strip()
        return [{"page": None, "text": text}]
    else:
        logger.warning("Unsupported file type: %s", ext)
        return []


def _extract_pdf(content: bytes, key: str) -> list[dict]:
    """Extract text from PDF bytes using PyPDF2."""
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page": i + 1, "text": text.strip()})
    logger.info("Extracted %d pages from %s", len(pages), key)
    return pages


def _get_image_format(ext: str) -> str:
    fmt_map = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tiff": "tiff", ".bmp": "bmp"}
    return fmt_map.get(ext, "png")


# ─── Text Chunking ───────────────────────────────────────────────────────────

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


def chunk_text(text: str, source_uri: str, page: int | None = None) -> list[dict]:
    """Split text into overlapping chunks."""
    if not text.strip():
        return []

    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current = ""
    idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= CHUNK_SIZE:
            current = f"{current}\n{para}".strip() if current else para
        else:
            if current:
                chunks.append({"text": current, "source_uri": source_uri, "page": page, "chunk_index": idx})
                idx += 1
                current = current[-CHUNK_OVERLAP:] + "\n" + para if CHUNK_OVERLAP else para
            else:
                for start in range(0, len(para), CHUNK_SIZE - CHUNK_OVERLAP):
                    segment = para[start:start + CHUNK_SIZE]
                    chunks.append({"text": segment, "source_uri": source_uri, "page": page, "chunk_index": idx})
                    idx += 1
                current = ""

    if current.strip():
        chunks.append({"text": current.strip(), "source_uri": source_uri, "page": page, "chunk_index": idx})

    return chunks


def chunk_document_pages(pages: list[dict], source_uri: str) -> list[dict]:
    """Chunk all pages of a document."""
    all_chunks = []
    for page_data in pages:
        all_chunks.extend(chunk_text(page_data["text"], source_uri, page_data.get("page")))
    return all_chunks


# ─── Entity/Relation Extraction ──────────────────────────────────────────────

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


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def extract_from_chunk(chunk: dict) -> dict | None:
    """Extract entities and relations from a text chunk using Nova."""
    prompt = f"""Extract entities and relationships from the following text chunk:

---
{chunk['text']}
---

Source: {chunk['source_uri']}, Page: {chunk.get('page', 'N/A')}

Return the JSON extraction result."""

    try:
        raw = invoke_nova_text(prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT, max_tokens=2048)
        data = json.loads(_strip_json_fences(raw))
        return {
            "entities": data.get("entities", []),
            "relations": data.get("relations", []),
            "source_uri": chunk["source_uri"],
            "page": chunk.get("page"),
            "span": chunk["text"][:100],
        }
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Extraction parse error: %s", exc)
        return None


def extract_from_image(image_bytes: bytes, image_format: str, source_uri: str) -> dict | None:
    """Extract entities and relations from an image using Nova multimodal."""
    prompt = (
        "Extract all entities and relationships visible in this image. "
        "Return ONLY JSON in the format: "
        '{"entities": [{"label": "...", "type": "...", "aliases": [], "confidence": 0.9}], '
        '"relations": [{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9}]}'
    )

    try:
        raw = invoke_nova_multimodal(prompt, image_bytes, image_format, system_prompt=EXTRACTION_SYSTEM_PROMPT, max_tokens=2048)
        data = json.loads(_strip_json_fences(raw))
        return {
            "entities": data.get("entities", []),
            "relations": data.get("relations", []),
            "source_uri": source_uri,
            "page": None,
            "span": f"[image: {Path(source_uri).name}]",
        }
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Image extraction error: %s", exc)
        return None


# ─── Entity Deduplication (cosine similarity via embeddings) ──────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def deduplicate_entities(extractions: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> tuple[dict, list[dict]]:
    """Deduplicate entities across all extraction results using embeddings.

    Returns (merge_map, unique_entities).
    """
    merge_map: dict[str, str] = {}
    unique_entities: list[dict] = []
    seen: dict[str, dict] = {}
    embeddings: dict[str, list[float]] = {}

    all_entities = []
    for ext in extractions:
        all_entities.extend(ext.get("entities", []))

    for entity in all_entities:
        label = entity.get("label", "").strip()
        if not label:
            continue

        if label in seen:
            merge_map[label] = label
            continue

        try:
            emb = get_text_embedding(label)
        except Exception as exc:
            logger.warning("Embedding failed for '%s': %s", label, exc)
            seen[label] = entity
            unique_entities.append(entity)
            merge_map[label] = label
            continue

        # Check similarity against existing entities
        best_match = None
        best_score = 0.0
        for existing_label, existing_emb in embeddings.items():
            score = _cosine_similarity(emb, existing_emb)
            if score > best_score:
                best_score = score
                best_match = existing_label

        if best_match and best_score >= threshold:
            merge_map[label] = best_match
            if label not in seen.get(best_match, {}).get("aliases", []):
                seen[best_match].setdefault("aliases", []).append(label)
            logger.info("Merged '%s' -> '%s' (similarity=%.3f)", label, best_match, best_score)
        else:
            embeddings[label] = emb
            seen[label] = entity
            unique_entities.append(entity)
            merge_map[label] = label

    logger.info("Deduplication: %d total -> %d unique entities", len(all_entities), len(unique_entities))
    return merge_map, unique_entities


# ─── Knowledge Graph (in-memory, per invocation context) ─────────────────────
# NOTE: Lambda keeps the execution context warm between invocations,
# so the graph persists across requests within the same warm container.

class KnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self.documents: dict[str, dict] = {}

    def add_node(self, node: dict):
        self.nodes[node["id"]] = node

    def add_edge(self, edge: dict):
        self.edges[edge["id"]] = edge

    def get_node_by_label(self, label: str) -> dict | None:
        for node in self.nodes.values():
            if node["label"].lower() == label.lower():
                return node
            if label.lower() in [a.lower() for a in node.get("aliases", [])]:
                return node
        return None

    def get_facts_text(self, node_ids: list[str] | None = None) -> str:
        lines = []
        edges_to_show = self.edges.values()
        if node_ids:
            node_set = set(node_ids)
            edges_to_show = [
                e for e in self.edges.values()
                if e["subject_id"] in node_set or e["object_id"] in node_set
            ]

        for edge in edges_to_show:
            subj = self.nodes.get(edge["subject_id"])
            obj = self.nodes.get(edge["object_id"])
            if subj and obj:
                cite = ""
                prov = edge.get("provenance", {})
                if prov.get("source_uri"):
                    cite = f" [source: {prov['source_uri']}"
                    if prov.get("page"):
                        cite += f", page {prov['page']}"
                    cite += "]"
                lines.append(
                    f"- {subj['label']} --[{edge['predicate']}]--> {obj['label']} "
                    f"(confidence: {edge['confidence']}){cite}"
                )
        return "\n".join(lines)

    def summary(self) -> str:
        return f"{len(self.nodes)} nodes, {len(self.edges)} edges, {len(self.documents)} documents ingested"

    def reset(self):
        self.nodes.clear()
        self.edges.clear()
        self.documents.clear()


# Global singleton — persists across warm Lambda invocations
_kg = KnowledgeGraph()


def _make_node_id(label: str) -> str:
    return label.lower().replace(" ", "_").replace("-", "_")


# ─── Graph Building Pipeline ─────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def build_graph_from_s3(bucket: str, s3_keys: list[str]) -> tuple[list[dict], list[dict], str]:
    """Full pipeline: S3 download → extract text → chunk → extract entities → dedup → build graph."""
    global _kg
    _kg.reset()

    all_chunks = []
    all_extractions = []

    for key in s3_keys:
        ext = Path(key).suffix.lower()
        source_uri = f"s3://{bucket}/{key}"

        _kg.documents[key] = {"name": Path(key).name, "uri": source_uri}

        pages = extract_text_from_s3(bucket, key)

        if ext in IMAGE_EXTENSIONS:
            for page_data in pages:
                img_bytes = page_data.get("image_bytes")
                img_fmt = page_data.get("image_format", "png")
                if img_bytes:
                    result = extract_from_image(img_bytes, img_fmt, source_uri)
                    if result and (result["entities"] or result["relations"]):
                        all_extractions.append(result)
        else:
            chunks = chunk_document_pages(pages, source_uri)
            all_chunks.extend(chunks)

    # Extract entities/relations from text chunks
    if all_chunks:
        for chunk in all_chunks:
            result = extract_from_chunk(chunk)
            if result and (result["entities"] or result["relations"]):
                all_extractions.append(result)

    if not all_extractions:
        return [], [], "No entities or relations extracted."

    # Deduplicate
    merge_map, unique_entities = deduplicate_entities(all_extractions)

    # Build nodes
    for entity in unique_entities:
        node_id = _make_node_id(entity["label"])
        node = {
            "id": node_id,
            "type": "Entity",
            "label": entity["label"],
            "aliases": entity.get("aliases", []),
            "confidence": entity.get("confidence", 1.0),
            "status": "active",
            "properties": {"entity_type": entity.get("type", "Unknown")},
        }
        _kg.add_node(node)

    # Build edges
    for extraction in all_extractions:
        for rel in extraction.get("relations", []):
            subj_label = merge_map.get(rel["subject"], rel["subject"])
            obj_label = merge_map.get(rel["object"], rel["object"])
            subj_id = _make_node_id(subj_label)
            obj_id = _make_node_id(obj_label)

            # Ensure both nodes exist
            if subj_id not in _kg.nodes:
                _kg.add_node({"id": subj_id, "type": "Entity", "label": subj_label,
                              "aliases": [], "confidence": 0.7, "status": "active",
                              "properties": {"entity_type": "Unknown"}})
            if obj_id not in _kg.nodes:
                _kg.add_node({"id": obj_id, "type": "Entity", "label": obj_label,
                              "aliases": [], "confidence": 0.7, "status": "active",
                              "properties": {"entity_type": "Unknown"}})

            edge_id = str(uuid.uuid4())[:8]
            edge = {
                "id": edge_id,
                "subject_id": subj_id,
                "predicate": rel["predicate"],
                "object_id": obj_id,
                "provenance": {
                    "source_uri": extraction.get("source_uri", ""),
                    "page": extraction.get("page"),
                    "span": extraction.get("span"),
                },
                "effective_from": rel.get("effective_from"),
                "confidence": rel.get("confidence", 1.0),
            }
            _kg.add_edge(edge)

    summary = f"Graph built: {len(_kg.nodes)} entities, {len(_kg.edges)} relations from {len(s3_keys)} document(s)."
    logger.info(summary)
    return list(_kg.nodes.values()), list(_kg.edges.values()), summary


# ─── Query Service ────────────────────────────────────────────────────────────

QUERY_SYSTEM_PROMPT = """You are a knowledge graph question-answering assistant.
You are given a set of facts from a knowledge graph and a user question.

Rules:
1. Answer ONLY based on the provided facts. Do NOT make up information.
2. If the facts don't contain enough info, say so honestly.
3. Always cite the source for each claim.
4. Return your response as JSON in this exact format:

{
  "answer": "A concise natural language answer.",
  "items": [
    {
      "subject": "...",
      "predicate": "...",
      "object": "...",
      "citations": [{"source_uri": "...", "page": null, "span": "..."}]
    }
  ]
}

Return ONLY the JSON — no markdown fences, no extra text."""

IDENTIFY_ENTITIES_PROMPT = """Given the following question, identify the key entity names that should be looked up in a knowledge graph.

Question: {question}

Available entities in the graph:
{entity_list}

Return ONLY a JSON array of the most relevant entity labels from the available list. Example: ["Payment Service", "Auth Service"]
Do NOT include entities not in the list. Return at most 5."""


def _identify_relevant_entities(question: str) -> list[str]:
    entity_labels = [node["label"] for node in _kg.nodes.values()]
    if not entity_labels:
        return []

    prompt = IDENTIFY_ENTITIES_PROMPT.format(question=question, entity_list=", ".join(entity_labels))
    try:
        raw = invoke_nova_text(prompt, max_tokens=512)
        return json.loads(_strip_json_fences(raw))
    except Exception as exc:
        logger.warning("Entity identification failed: %s", exc)
        return []


def query_knowledge_graph(question: str) -> dict:
    """Answer a question using the knowledge graph + Nova reasoning."""
    if not _kg.nodes:
        return {"answer": "No knowledge graph has been built yet. Please load documents and build the graph first.", "items": []}

    # Step 1: Identify relevant entities
    relevant_labels = _identify_relevant_entities(question)

    # Step 2: Get relevant facts
    if relevant_labels:
        relevant_ids = []
        for label in relevant_labels:
            node = _kg.get_node_by_label(label)
            if node:
                relevant_ids.append(node["id"])
        facts_text = _kg.get_facts_text(node_ids=relevant_ids) if relevant_ids else _kg.get_facts_text()
    else:
        facts_text = _kg.get_facts_text()

    if not facts_text.strip():
        return {"answer": "The knowledge graph has no relevant facts to answer this question.", "items": []}

    # Step 3: Reason with Nova
    prompt = f"""Knowledge Graph Facts:
{facts_text}

User Question: {question}

Analyze the facts and answer the question. Return JSON as specified."""

    try:
        raw = invoke_nova_text(prompt, system_prompt=QUERY_SYSTEM_PROMPT, max_tokens=2048)
        data = json.loads(_strip_json_fences(raw))
        return {
            "answer": data.get("answer", "Unable to generate answer."),
            "items": data.get("items", []),
        }
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Query reasoning failed: %s", exc)
        return {"answer": f"Error processing query: {exc}", "items": []}


# ─── Route Handlers ───────────────────────────────────────────────────────────

def handle_list_documents(body: dict) -> dict:
    """List files in S3 bucket with given prefix."""
    bucket = body.get("bucket", "")
    prefix = body.get("prefix", "")

    if not bucket:
        return _error_response(400, "Missing 'bucket' parameter")

    try:
        params = {"Bucket": bucket, "MaxKeys": 1000}
        if prefix:
            params["Prefix"] = prefix

        response = s3_client.list_objects_v2(**params)
        documents = []

        for obj in response.get("Contents", []):
            key = obj["Key"]
            # Skip directories and hidden files
            if key.endswith("/") or "/." in key:
                continue
            # Only include supported file types
            ext = Path(key).suffix.lower()
            if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".tiff", ".bmp"}:
                continue

            documents.append({
                "key": key,
                "name": Path(key).name,
                "bucket": bucket,
                "size": obj.get("Size", 0),
                "last_modified": obj.get("LastModified", "").isoformat() if obj.get("LastModified") else None,
            })

        return {"statusCode": 200, "body": {"documents": documents}}

    except Exception as exc:
        logger.exception("Failed to list S3 documents")
        return _error_response(500, f"Failed to list documents: {str(exc)}")


def handle_build_graph(body: dict) -> dict:
    """Build knowledge graph from S3 documents."""
    bucket = body.get("bucket", "")
    s3_keys = body.get("s3_keys", [])

    if not bucket:
        return _error_response(400, "Missing 'bucket' parameter")
    if not s3_keys:
        return _error_response(400, "No S3 keys provided")

    try:
        nodes, edges, summary = build_graph_from_s3(bucket, s3_keys)
        return {
            "statusCode": 200,
            "body": {"nodes": nodes, "edges": edges, "summary": summary},
        }
    except Exception as exc:
        logger.exception("Graph build failed")
        return _error_response(500, f"Build failed: {str(exc)}")


def handle_query(body: dict) -> dict:
    """Query the knowledge graph."""
    question = body.get("question", "").strip()
    if not question:
        return _error_response(400, "Missing 'question' parameter")

    try:
        result = query_knowledge_graph(question)
        return {"statusCode": 200, "body": result}
    except Exception as exc:
        logger.exception("Query failed")
        return _error_response(500, f"Query failed: {str(exc)}")


def handle_graph_stats(body: dict) -> dict:
    """Return graph statistics."""
    return {
        "statusCode": 200,
        "body": {
            "node_count": len(_kg.nodes),
            "edge_count": len(_kg.edges),
            "document_count": len(_kg.documents),
            "summary": _kg.summary(),
        },
    }


def handle_reset(body: dict) -> dict:
    """Reset the knowledge graph."""
    _kg.reset()
    return {"statusCode": 200, "body": {"status": "Graph reset successfully"}}


def _error_response(status_code: int, message: str) -> dict:
    return {"statusCode": status_code, "body": {"detail": message}}


# ─── Route Map ────────────────────────────────────────────────────────────────

ROUTES = {
    "/list-documents": handle_list_documents,
    "/build-graph": handle_build_graph,
    "/query": handle_query,
    "/graph-stats": handle_graph_stats,
    "/reset": handle_reset,
}


# ─── Lambda Handler ───────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """Main Lambda entry point. Supports Lambda Function URL and API Gateway."""
    logger.info("Event: %s", json.dumps(event, default=str)[:2000])

    # Determine the path
    path = "/"
    if "rawPath" in event:
        # Lambda Function URL
        path = event["rawPath"]
    elif "path" in event:
        # API Gateway REST
        path = event["path"]
    elif "requestContext" in event and "http" in event.get("requestContext", {}):
        path = event["requestContext"]["http"].get("path", "/")

    # Handle CORS preflight
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if not http_method:
        http_method = event.get("httpMethod", "POST")

    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": "",
        }

    # Parse body
    body = {}
    raw_body = event.get("body", "")
    if raw_body:
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            pass

    # Route to handler
    handler = ROUTES.get(path)
    if not handler:
        # Try stripping trailing slash or matching partial path
        clean_path = path.rstrip("/")
        handler = ROUTES.get(clean_path)

    if not handler:
        result = _error_response(404, f"Unknown route: {path}")
    else:
        result = handler(body)

    return {
        "statusCode": result["statusCode"],
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(result["body"], default=str),
    }
