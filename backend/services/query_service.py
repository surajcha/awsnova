"""Natural language query service over the knowledge graph."""

from __future__ import annotations

import json
import logging

from models.schemas import GraphNode, Provenance, QueryItem, QueryResponse
from services.graph_service import get_knowledge_graph
from utils.bedrock_client import invoke_nova_text

logger = logging.getLogger(__name__)

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

QUERY_USER_PROMPT = """Knowledge Graph Facts:
{facts}

User Question: {question}

Analyze the facts and answer the question. Return JSON as specified."""

IDENTIFY_ENTITIES_PROMPT = """Given the following question, identify the key entity names that should be looked up in a knowledge graph.

Question: {question}

Available entities in the graph:
{entity_list}

Return ONLY a JSON array of the most relevant entity labels from the available list. Example: ["Payment Service", "Auth Service"]
Do NOT include entities not in the list. Return at most 5."""


def _identify_relevant_entities(question: str) -> list[str]:
    """Use Nova to identify which entities the question is about."""
    kg = get_knowledge_graph()

    entity_labels = [node.label for node in kg.nodes.values()]
    if not entity_labels:
        return []

    prompt = IDENTIFY_ENTITIES_PROMPT.format(
        question=question,
        entity_list=", ".join(entity_labels),
    )

    try:
        raw = invoke_nova_text(prompt, max_tokens=512)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        return json.loads(raw.strip())
    except Exception as exc:
        logger.warning("Entity identification failed: %s", exc)
        return []


def query_graph(question: str) -> QueryResponse:
    """Answer a natural-language question using the knowledge graph + Nova reasoning."""
    kg = get_knowledge_graph()

    if not kg.nodes:
        return QueryResponse(
            answer="No knowledge graph has been built yet. Please upload documents and build the graph first.",
            items=[],
        )

    # Step 1: Identify relevant entities
    relevant_labels = _identify_relevant_entities(question)

    # Step 2: Get relevant subgraph facts
    if relevant_labels:
        relevant_ids = []
        for label in relevant_labels:
            node = kg.get_node_by_label(label)
            if node:
                relevant_ids.append(node.id)

        if relevant_ids:
            facts_text = kg.get_facts_text(node_ids=relevant_ids)
        else:
            facts_text = kg.get_facts_text()
    else:
        # Fallback: use all facts (for small graphs this is fine)
        facts_text = kg.get_facts_text()

    if not facts_text.strip():
        return QueryResponse(
            answer="The knowledge graph has no relevant facts to answer this question.",
            items=[],
        )

    # Step 3: Reason with Nova
    prompt = QUERY_USER_PROMPT.format(facts=facts_text, question=question)

    try:
        raw = invoke_nova_text(prompt, system_prompt=QUERY_SYSTEM_PROMPT, max_tokens=2048)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        items = []
        for item_data in data.get("items", []):
            citations = [
                Provenance(**c) for c in item_data.get("citations", [])
            ]
            items.append(QueryItem(
                subject=item_data.get("subject", ""),
                predicate=item_data.get("predicate", ""),
                object=item_data.get("object", ""),
                citations=citations,
            ))

        return QueryResponse(
            answer=data.get("answer", "Unable to generate answer."),
            items=items,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Query reasoning failed: %s", exc)
        return QueryResponse(
            answer=f"Error processing query: {exc}",
            items=[],
        )
