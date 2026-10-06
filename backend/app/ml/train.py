"""
Trains the skill recommendation model.

Approach: item-based collaborative filtering.
  1. Each row of data/skill_profiles.csv is one learner's set of skills.
  2. Build a binary profile x skill matrix (1 = this learner has this skill).
  3. Cosine similarity between skill columns = which skills people tend to have together.
  4. Save similarity matrix, vocabulary and popularity to model.pkl with Pickle.

Run:  python -m app.ml.train      (Docker runs it at build time)
"""
import csv
import pickle
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA = BACKEND_DIR / "data" / "skill_profiles.csv"
MODEL = BACKEND_DIR / "data" / "model.pkl"


def normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def train(data_path: Path = DATA, model_path: Path = MODEL) -> dict:
    profiles: list[list[str]] = []
    display: dict[str, str] = {}          # normalised key -> original spelling for display
    with open(data_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keys = []
            for skill in (s for s in row["skills"].split("|") if s.strip()):
                key = normalize(skill)
                display.setdefault(key, skill.strip())
                keys.append(key)
            if keys:
                profiles.append(sorted(set(keys)))

    vocab = sorted(display)
    index = {skill: i for i, skill in enumerate(vocab)}
    matrix = np.zeros((len(profiles), len(vocab)), dtype=np.float32)
    for r, keys in enumerate(profiles):
        for key in keys:
            matrix[r, index[key]] = 1.0

    similarity = cosine_similarity(matrix.T)      # skill x skill
    np.fill_diagonal(similarity, 0.0)             # a skill shouldn't recommend itself
    popularity = matrix.sum(axis=0)
    popularity = popularity / popularity.max()

    model = {
        "version": 1,
        "vocab": vocab,
        "index": index,
        "display": display,
        "similarity": similarity.astype(np.float32),
        "popularity": popularity.astype(np.float32),
        "n_profiles": len(profiles),
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    return model


if __name__ == "__main__":
    m = train()
    print(f"Trained on {m['n_profiles']} profiles, {len(m['vocab'])} skills -> {MODEL}")
