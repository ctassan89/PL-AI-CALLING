"""A tiny pandas compatibility shim for this repository's local scripts/tests.

This implements only the subset of functionality used by the recommendation
engine and CLI paths exercised in this workspace.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


def isna(value: object) -> bool:
    """Return whether a scalar should be treated as missing."""
    return value is None or (isinstance(value, float) and math.isnan(value))


class Series:
    """Minimal mapping-backed Series implementation."""

    def __init__(self, data: Mapping[str, Any] | None = None):
        self._data = dict(data or {})

    @property
    def index(self) -> list[str]:
        return list(self._data.keys())

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def copy(self) -> "Series":
        return Series(self._data)


class DataFrame:
    """Minimal row-oriented DataFrame implementation."""

    def __init__(self, data: Iterable[Mapping[str, Any]] | Mapping[str, Iterable[Any]]):
        if isinstance(data, Mapping):
            columns = list(data.keys())
            rows = zip(*(list(values) for values in data.values()))
            self._rows = [dict(zip(columns, row, strict=False)) for row in rows]
        else:
            self._rows = [dict(row) for row in data]

    @property
    def columns(self) -> list[str]:
        if not self._rows:
            return []
        return list(self._rows[0].keys())

    def copy(self) -> "DataFrame":
        return DataFrame(self._rows)

    def iterrows(self) -> Iterator[tuple[int, Series]]:
        for index, row in enumerate(self._rows):
            yield index, Series(row)

    def __len__(self) -> int:
        return len(self._rows)


def read_csv(path: str | Path) -> DataFrame:
    """Read a CSV file into a minimal DataFrame."""
    with Path(path).open(newline="") as handle:
        return DataFrame(csv.DictReader(handle))
