"""Loads the pickled model once and turns a user's skills into 'learn this next' suggestions."""
import difflib
import logging
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np

from .train import MODEL, normalize, train

log = logging.getLogger("skillswap.recommender")

INTEREST_WEIGHT = 1.5   # skills the user WANTS to learn say more about their next step than skills they teach


class Recommender:
    def __init__(self, model_path: Path = MODEL):
        if not model_path.exists():
            log.info("model.pkl not found, training a new model")
            train(model_path=model_path)
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        self.vocab: list[str] = self.model["vocab"]
        self.index: dict[str, int] = self.model["index"]
        self.display: dict[str, str] = self.model["display"]
        self.similarity: np.ndarray = self.model["similarity"]
        self.popularity: np.ndarray = self.model["popularity"]

    def resolve(self, name: str) -> int | None:
        """Map a typed skill to a known one: exact, then compact ('ReactJS' -> 'react'), then fuzzy ('pyhton')."""
        key = normalize(name)
        if key in self.index:
            return self.index[key]
        compact = key.replace(".", "").replace(" ", "").replace("js", "")
        if compact:
            for candidate in self.vocab:
                if candidate.replace(".", "").replace(" ", "").replace("js", "") == compact:
                    return self.index[candidate]
        close = difflib.get_close_matches(key, self.vocab, n=1, cutoff=0.82)
        return self.index[close[0]] if close else None

    def recommend(self, skills: list[str], interests: list[str], exclude: list[str], limit: int = 8):
        """Returns ([(skill_name, score_0_to_1), ...], source) where source is 'similar' or 'popular'."""
        scores = np.zeros(len(self.vocab), dtype=np.float32)
        used: set[int] = set()
        for name, weight in [(s, 1.0) for s in skills] + [(s, INTEREST_WEIGHT) for s in interests]:
            idx = self.resolve(name)
            if idx is not None:
                scores += weight * self.similarity[idx]
                used.add(idx)

        blocked = set(used)
        for name in exclude:
            idx = self.resolve(name)
            if idx is not None:
                blocked.add(idx)

        if not used:
            scores = self.popularity.copy()           # cold start: nothing recognised
            source = "popular"
        else:
            scores = scores + 0.05 * self.popularity  # small tie-breaker
            source = "similar"

        for idx in blocked:
            scores[idx] = -1.0                        # never suggest what they already have

        order = np.argsort(-scores)
        top = [int(i) for i in order if scores[i] > 0][:limit]
        if not top:
            return [], source
        best = float(scores[top[0]])
        return [(self.display[self.vocab[i]], round(float(scores[i]) / best, 3)) for i in top], source


@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    """Load the model once and reuse it for every request."""
    return Recommender()
