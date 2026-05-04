"""Recommendation helpers."""

from __future__ import annotations

from typing import Any

__all__ = ["build_situation", "recommend_plays", "score_play"]


def build_situation(*args: Any, **kwargs: Any) -> dict[str, str | int]:
    """Proxy build_situation lazily so lightweight modules avoid pandas import."""
    from .engine import build_situation as engine_build_situation

    return engine_build_situation(*args, **kwargs)


def recommend_plays(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """Proxy recommend_plays lazily so lightweight modules avoid pandas import."""
    from .engine import recommend_plays as engine_recommend_plays

    return engine_recommend_plays(*args, **kwargs)


def score_play(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Proxy score_play lazily so lightweight modules avoid pandas import."""
    from .engine import score_play as engine_score_play

    return engine_score_play(*args, **kwargs)
