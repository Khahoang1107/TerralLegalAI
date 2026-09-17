"""Conservative rule-based extraction of Vietnamese amendment references."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass


@dataclass
class ArticleChange:
    action: str
    article: str
    clause: str = ""
    point: str = ""
    evidence_text: str = ""
    confidence: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_label(value: str | None) -> str:
    value = unicodedata.normalize("NFC", value or "").casefold()
    return " ".join(value.replace(".", " ").split())


class ArticleMapper:
    """Extract only explicit legal references; ambiguous cases require review."""

    CHANGE_RE = re.compile(
        r"(?P<verb>bãi\s+bỏ|sửa\s+đổi(?:\s*,?\s*bổ\s+sung)?|bổ\s+sung|thay\s+thế)"
        r"(?P<body>.{0,240}?)"
        r"(?:(?P<point>điểm\s+[a-zđ])\s+(?:tại\s+)?)?"
        r"(?:(?P<clause>khoản\s+\d+[a-zđ]?)\s+(?:tại\s+)?)?"
        r"(?P<article>điều\s+\d+[a-zđ]?)",
        re.IGNORECASE | re.DOTALL,
    )

    @staticmethod
    def _action(verb: str, body: str = "") -> str:
        normalized = normalize_label(verb)
        if "bãi bỏ" in normalized:
            return "repeal"
        if "thay thế" in normalized:
            if "cụm từ" in normalize_label(body):
                return "replace_text"
            return "replace"
        if normalized.startswith("bổ sung"):
            return "add"
        return "amend"

    def extract_changes(self, text: str) -> list[ArticleChange]:
        changes: list[ArticleChange] = []
        seen: set[tuple[str, str, str, str]] = set()
        for match in self.CHANGE_RE.finditer(text or ""):
            evidence = " ".join(match.group(0).split())[:500]
            change = ArticleChange(
                action=self._action(match.group("verb"), match.group("body")),
                article=match.group("article").title(),
                clause=(match.group("clause") or "").title(),
                point=(match.group("point") or "").title(),
                evidence_text=evidence,
                confidence=0.96 if match.group("clause") or match.group("point") else 0.90,
            )
            key = (change.action, normalize_label(change.article), normalize_label(change.clause), normalize_label(change.point))
            if key not in seen:
                seen.add(key)
                changes.append(change)
        return changes
