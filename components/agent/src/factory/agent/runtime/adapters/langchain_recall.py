"""Compose Agent recall middleware without owning recall behavior."""
from __future__ import annotations


def build_recall_middleware() -> tuple[object, object]:
    from .langchain_hybrid_recall import (
        HybridRecallMCP, LangChainHybridRecallMiddleware,
    )
    from .langchain_lessons import LangChainLessonsMiddleware, LessonsRecallMCP

    return (
        LangChainLessonsMiddleware(LessonsRecallMCP()),
        LangChainHybridRecallMiddleware(HybridRecallMCP()),
    )


__all__ = ["build_recall_middleware"]
