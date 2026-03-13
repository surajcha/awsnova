"""Text chunking service — splits extracted pages into manageable chunks."""

from __future__ import annotations

import re
from models.schemas import TextChunk

DEFAULT_CHUNK_SIZE = 1500  # characters
DEFAULT_OVERLAP = 200


def chunk_text(
    text: str,
    source_uri: str,
    page: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """Split text into overlapping chunks.

    Uses paragraph boundaries when possible, falling back to character splits.
    """
    if not text.strip():
        return []

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[TextChunk] = []
    current = ""
    chunk_idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}".strip() if current else para
        else:
            if current:
                chunks.append(TextChunk(
                    text=current,
                    source_uri=source_uri,
                    page=page,
                    chunk_index=chunk_idx,
                ))
                chunk_idx += 1
                # Keep overlap from end of current chunk
                current = current[-overlap:] + "\n" + para if overlap else para
            else:
                # Single paragraph larger than chunk_size — force-split by characters
                for start in range(0, len(para), chunk_size - overlap):
                    segment = para[start : start + chunk_size]
                    chunks.append(TextChunk(
                        text=segment,
                        source_uri=source_uri,
                        page=page,
                        chunk_index=chunk_idx,
                    ))
                    chunk_idx += 1
                current = ""

    # Flush remaining
    if current.strip():
        chunks.append(TextChunk(
            text=current.strip(),
            source_uri=source_uri,
            page=page,
            chunk_index=chunk_idx,
        ))

    return chunks


def chunk_document_pages(
    pages: list[dict],
    source_uri: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """Chunk all pages of a document."""
    all_chunks: list[TextChunk] = []
    for page_data in pages:
        page_chunks = chunk_text(
            text=page_data["text"],
            source_uri=source_uri,
            page=page_data.get("page"),
            chunk_size=chunk_size,
            overlap=overlap,
        )
        all_chunks.extend(page_chunks)
    return all_chunks
