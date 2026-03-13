"""Amazon Bedrock client wrapper for invoking Nova models."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import boto3

from config import settings

logger = logging.getLogger(__name__)

_bedrock_runtime = None


def _get_client():
    global _bedrock_runtime
    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    return _bedrock_runtime


def invoke_nova_text(prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> str:
    """Invoke Nova Pro/Lite for text generation (extraction, reasoning, QA)."""
    client = _get_client()

    messages = [{"role": "user", "content": [{"text": prompt}]}]
    system = [{"text": system_prompt}] if system_prompt else []

    body = {
        "messages": messages,
        "inferenceConfig": {
            "maxNewTokens": max_tokens,
            "temperature": 0.1,
            "topP": 0.9,
        },
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=settings.NOVA_TEXT_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def invoke_nova_multimodal(
    prompt: str,
    image_path: str | None = None,
    image_bytes: bytes | None = None,
    system_prompt: str = "",
    max_tokens: int = 4096,
) -> str:
    """Invoke Nova Lite for multimodal (text+image) tasks."""
    client = _get_client()

    content = []

    if image_path or image_bytes:
        if image_path and not image_bytes:
            image_bytes = Path(image_path).read_bytes()

        suffix = Path(image_path).suffix.lower() if image_path else ".png"
        media_type_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
        media_type = media_type_map.get(suffix, "image/png")

        content.append({
            "image": {
                "format": media_type.split("/")[1],
                "source": {"bytes": base64.b64encode(image_bytes).decode("utf-8")},
            }
        })

    content.append({"text": prompt})

    messages = [{"role": "user", "content": content}]
    system = [{"text": system_prompt}] if system_prompt else []

    body = {
        "messages": messages,
        "inferenceConfig": {
            "maxNewTokens": max_tokens,
            "temperature": 0.1,
            "topP": 0.9,
        },
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=settings.NOVA_LITE_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def get_text_embedding(text: str) -> list[float]:
    """Generate text embedding using Titan Embed Text v2."""
    client = _get_client()

    body = {
        "inputText": text[:8192],  # Titan v2 limit
        "dimensions": 1024,
        "normalize": True,
    }

    response = client.invoke_model(
        modelId=settings.NOVA_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(response["body"].read())
    return result["embedding"]


def get_multimodal_embedding(
    text: str | None = None,
    image_bytes: bytes | None = None,
) -> list[float]:
    """Generate multimodal embedding using Titan Embed Image v1."""
    client = _get_client()

    body = {}
    if text:
        body["inputText"] = text[:128]  # Titan image embed text limit
    if image_bytes:
        body["inputImage"] = base64.b64encode(image_bytes).decode("utf-8")

    response = client.invoke_model(
        modelId=settings.NOVA_MULTIMODAL_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(response["body"].read())
    return result["embedding"]
