from __future__ import annotations


class QueryNormalizationPolicy:
    """Unordered tokens may be sorted; phrase order and nickname semantics are preserved."""

    def normalize(self, text: str, *, mode: str, language: str) -> tuple[str, ...]:
        raise NotImplementedError("Versioned Unicode/case/token/language normalization")
