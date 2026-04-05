"""
Gemini Embedding 2 wrapper for multimodal document embedding.

All modalities (text, images, tables) go through gemini-embedding-2-preview
via the google-genai SDK, producing vectors in a single shared 3072-dimensional
space so cross-modal cosine similarity is meaningful.
"""

import asyncio
import logging
import os
import time
from typing import Optional

import numpy as np
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODEL_ID = "gemini-embedding-2-preview"
EMBEDDING_DIM = 3072
MAX_IMAGES_PER_REQUEST = 6
BATCH_SIZE = 5  # max pages per batch (interleaved image+text)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a key at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def l2_normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def _embed_content_sync(contents, config=None):
    """Synchronous embed call with exponential backoff on 429/503."""
    client = get_client()
    if config is None:
        config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = client.models.embed_content(
                model=MODEL_ID,
                contents=contents,
                config=config,
            )
            return result
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "503" in error_str:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                        f"retrying in {delay:.1f}s: {error_str}"
                    )
                    time.sleep(delay)
                    continue
            raise
    raise last_error


async def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns (3072,) L2-normalized float32."""
    result = await asyncio.to_thread(
        _embed_content_sync,
        types.Content(parts=[types.Part(text=text)]),
    )
    vec = np.array(result.embeddings[0].values, dtype=np.float32)
    return l2_normalize(vec)


async def embed_texts(texts: list[str]) -> np.ndarray:
    """Batch embed multiple texts. Returns (n, 3072) L2-normalized float32."""
    contents = [
        types.Content(parts=[types.Part(text=t)])
        for t in texts
    ]
    result = await asyncio.to_thread(
        _embed_content_sync,
        contents,
    )
    vectors = np.array(
        [e.values for e in result.embeddings],
        dtype=np.float32,
    )
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


async def embed_multimodal(
    text: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> np.ndarray:
    """Embed text + image together as a single content. Returns (3072,) L2-normalized."""
    result = await asyncio.to_thread(
        _embed_content_sync,
        types.Content(parts=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part(text=text),
        ]),
    )
    vec = np.array(result.embeddings[0].values, dtype=np.float32)
    return l2_normalize(vec)


