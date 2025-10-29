from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from heapq import nlargest
from typing import Iterable, Literal

from app.repo.indices.metrics import cosine, l2sq

log = logging.getLogger("vectordb")


@dataclass
class _Leaf:
    ids: list[str]


@dataclass
class _Node:
    # Internal node: split by hyperplane w·x >= b (b is median proj)
    w: list[float]
    b: float
    left: object  # _Node | _Leaf
    right: object  # _Node | _Leaf


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class _RPTree:
    def __init__(self, leaf_size: int, rng: random.Random):
        self.leaf_size = max(leaf_size, 4)
        self.rng = rng
        self.root: _Node | _Leaf | None = None
        self.vecs: list[list[float]] | None = None
        self.ids: list[str] | None = None

    def build(self, ids: list[str], vecs: list[list[float]]):
        self.ids = ids
        self.vecs = vecs
        idxs = list(range(len(ids)))
        self.root = self._build_node(idxs)

    def _random_vector(self, dim: int) -> list[float]:
        # Uniform on unit sphere by normalizing random normals
        v = [self.rng.normalvariate(0.0, 1.0) for _ in range(dim)]
        nrm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / nrm for x in v]

    def _build_node(self, idxs: list[int]) -> _Node | _Leaf:
        if len(idxs) <= self.leaf_size:
            return _Leaf(ids=[self.ids[i] for i in idxs])

        dim = len(self.vecs[0])
        tries = 0
        while tries < 5:
            w = self._random_vector(dim)
            projs = [(_dot(w, self.vecs[i]), i) for i in idxs]
            projs.sort(key=lambda t: t[0])
            mid = len(projs) // 2
            b = projs[mid][0]  # median projection
            left_idxs = [i for (p, i) in projs if p < b]
            right_idxs = [i for (p, i) in projs if p >= b]
            if left_idxs and right_idxs:
                left = self._build_node(left_idxs)
                right = self._build_node(right_idxs)
                return _Node(w=w, b=b, left=left, right=right)
            tries += 1

        # Fallback to leaf on pathological splits
        return _Leaf(ids=[self.ids[i] for i in idxs])

    def _descend(self, q: list[float]) -> _Leaf:
        node = self.root
        while isinstance(node, _Node):
            s = _dot(node.w, q)
            node = node.right if s >= node.b else node.left
        return node

    def candidates(self, q: list[float]) -> list[str]:
        leaf = self._descend(q)
        return leaf.ids[:]  # copy


class RPForestIndex:
    """
        Random Projection Forest (Annoy-style):
        - Build M trees with random hyperplanes.
        - Query: get leaf from each tree; Union candidates; Re-rank exact by chosen metric.
    """

    def __init__(self, metric: Literal["cosine", "l2"] = "cosine",
                 trees: int = 8, leaf_size: int = 64, seed: int = 42,
                 candidate_mult: float = 2.0):  # <-- NEW
        self.metric = metric
        self.trees = max(1, trees)
        self.leaf_size = max(1, leaf_size)
        self.seed = seed
        self.candidate_mult = max(0.1, float(candidate_mult))  # guard
        self._trees: list[_RPTree] = []
        self._id_to_vec: dict[str, list[float]] = {}

    def rebuild(self, pairs: Iterable[tuple[str, list[float]]]):
        ids, vecs = [], []
        for id_, v in pairs:
            ids.append(id_)
            vecs.append(v)

        N = len(ids)
        if self.leaf_size >= N:
            logging.info(
                f"[rp] leaf_size ({self.leaf_size}) >= N ({N}); tree will not partition; behavior ~exact"
            )

        self._id_to_vec = {i: v for i, v in zip(ids, vecs)}
        self._trees = []
        base_rng = random.Random(self.seed)
        for _ in range(self.trees):
            rng = random.Random(base_rng.random())  # different seed per tree
            t = _RPTree(leaf_size=self.leaf_size, rng=rng)
            t.build(ids, vecs)
            self._trees.append(t)

    def _score(self, q: list[float], v: list[float]) -> float:
        return cosine(q, v) if self.metric == "cosine" else -l2sq(q, v)

    def query(self, q: list[float], k: int) -> list[tuple[str, float]]:
        if not self._trees:
            return []
        # HARD LIMIT: gather at most candidate_mult * trees * leaf_size
        limit = max(k, int(self.trees * self.leaf_size * self.candidate_mult))
        cand_ids: set[str] = set()
        for tree in self._trees:
            # gather only from one leaf per tree
            cand_ids.update(tree.candidates(q))
            if len(cand_ids) >= limit:
                break

        # strictly enforce the cap
        if len(cand_ids) > limit:
            # trim deterministically by insertion order -> convert to list/slice
            cand_ids = list(cand_ids)[:limit]
        else:
            cand_ids = list(cand_ids)

        log.info(f"[rp] trees={self.trees} leaf_size={self.leaf_size} "
                 f"candidate_mult={self.candidate_mult} "
                 f"candidate_pool={len(cand_ids)}")

        scored = [(cid, self._score(q, self._id_to_vec[cid])) for cid in cand_ids]
        # re-rank exact within candidates
        return nlargest(k, scored, key=lambda t: t[1])
