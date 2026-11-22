"""Local embeddings via fastembed (ONNX, no API key, no torch)."""

from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

from common.settings import get_settings

EMBEDDING_DIM = 384


@lru_cache
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embedding_model)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _model().passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    return next(iter(_model().query_embed(text))).tolist()
