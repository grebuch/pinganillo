"""Send only the relevant part of the user's reference document.

The first version attached the whole document (up to 40,000 characters,
roughly 10,000 tokens) to every request, several times a minute. With a
ChatGPT plan that burns usage limits fast; with a local model it makes every
answer slow. The document rarely matters as a whole, so it is split into
passages and only the few that share vocabulary with what is being said are
sent, ranked with BM25.

BM25 is a classic search-engine ranking function. It is small, fast,
deterministic and needs no embedding model, which keeps the app local-first
and dependency-free. Synonyms are its weak spot; that is an accepted trade-off.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

MAX_DOCUMENT_CHARS = 200_000
PASSAGE_CHARS = 700
DEFAULT_BUDGET_CHARS = 2_500

# Already accent-folded, because tokens are folded before the lookup.
_STOPWORDS = frozenset(
    (  # noqa: SIM905  (one readable block per language)
        "the and for that this with from are was were have has had not but you your they them their "
        "what which who will would can could should about into than then there here when where while "
        "also just only very "
        "los las del que con para por una unos unas como pero sus mas este esta estos estas ese esa eso "
        "hay ser son fue han muy sin sobre entre cuando donde porque todo toda todos todas tambien "
        "les dels amb per uns unes com pero perque aquest aquesta molt sense quan"
    ).split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_normalise(text)) if len(t) > 2 and t not in _STOPWORDS]


def split_passages(text: str, size: int = PASSAGE_CHARS) -> list[str]:
    """Group paragraphs into passages of about ``size`` characters."""
    passages: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > size:  # very long paragraph: hard-wrap at a space
            cut = paragraph.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if current:
                passages.append(current)
                current = ""
            passages.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if current and len(current) + len(paragraph) + 2 > size:
            passages.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        passages.append(current)
    return passages


@dataclass
class KnowledgeBase:
    text: str = ""
    passage_chars: int = PASSAGE_CHARS
    k1: float = 1.5
    b: float = 0.75
    passages: list[str] = field(init=False, default_factory=list)
    _tf: list[Counter[str]] = field(init=False, default_factory=list, repr=False)
    _df: Counter[str] = field(init=False, default_factory=Counter, repr=False)
    _avg_len: float = field(init=False, default=0.0, repr=False)

    def __post_init__(self) -> None:
        if len(self.text) > MAX_DOCUMENT_CHARS:
            raise ValueError(f"Document too long (max {MAX_DOCUMENT_CHARS:,} characters).")
        self.passages = split_passages(self.text, self.passage_chars)
        self._tf = [Counter(tokenize(p)) for p in self.passages]
        for tf in self._tf:
            self._df.update(tf.keys())
        lengths = [sum(tf.values()) for tf in self._tf]
        self._avg_len = (sum(lengths) / len(lengths)) if lengths else 0.0

    def __bool__(self) -> bool:
        return bool(self.passages)

    def score(self, query: str) -> list[float]:
        terms = set(tokenize(query))
        n = len(self.passages)
        scores = []
        for tf in self._tf:
            length = sum(tf.values()) or 1
            total = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                total += (
                    idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / self._avg_len))
                )
            scores.append(total)
        return scores

    def relevant(self, query: str, budget_chars: int = DEFAULT_BUDGET_CHARS) -> str:
        """Best-matching passages that fit in ``budget_chars``, in document order.

        Returns an empty string when nothing in the document matches, so the
        model is not distracted by unrelated text.
        """
        if not self.passages:
            return ""
        scores = self.score(query)
        ranked = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: -scores[i])
        chosen: list[int] = []
        used = 0
        for i in ranked:
            cost = len(self.passages[i]) + 2
            if used + cost > budget_chars:
                continue
            chosen.append(i)
            used += cost
        return "\n\n".join(self.passages[i] for i in sorted(chosen))
