from __future__ import annotations
from heapq import nlargest
from typing import Iterable, Literal
from app.repo.indices.metrics import cosine, l2sq

class FlatIndex:
    def __init__(self, metric: Literal["cosine","l2"]="cosine"):
        self.ids: list[str] = []
        self.vecs: list[list[float]] = []
        self.metric = metric

    def rebuild(self, pairs: Iterable[tuple[str, list[float]]]):
        self.ids, self.vecs = [], []
        for id_, v in pairs:
            self.ids.append(id_)
            self.vecs.append(v)

    def query(self, q: list[float], k: int) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        scores = []
        if self.metric == "cosine":
            for id_, v in zip(self.ids, self.vecs):
                scores.append((id_, cosine(q, v)))
            # higher is better
            return nlargest(k, scores, key=lambda t: t[1])
        else:
            for id_, v in zip(self.ids, self.vecs):
                scores.append((id_, -l2sq(q, v)))  # negate so larger is better
            return nlargest(k, scores, key=lambda t: t[1])
