"""
Lightweight persistent vector index using NumPy + JSON files.
No external C++ dependencies — works on any platform.

Storage layout (inside app/vector_store/):
  chunks.json      — list of chunk metadata dicts (source, folder, start, text)
  embeddings.npy   — float32 array of shape (N, 384)
  fingerprint.txt  — hash of source file list to detect stale index
"""
import os
import json
import hashlib
import numpy as np
from typing import List, Optional

STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
CHUNKS_FILE = os.path.join(STORE_DIR, "chunks.json")
EMBEDDINGS_FILE = os.path.join(STORE_DIR, "embeddings.npy")
FINGERPRINT_FILE = os.path.join(STORE_DIR, "fingerprint.txt")


def _fingerprint(sources: List[str]) -> str:
    # Include the backend prefix so switching from local→S3 (or vice versa)
    # always invalidates the cached index even when file names are identical.
    import os
    backend = "s3:" + os.getenv("S3_BUCKET_NAME", "") if os.getenv("S3_BUCKET_NAME") else "local"
    payload = backend + "|" + "|".join(sorted(sources))
    return hashlib.md5(payload.encode()).hexdigest()


def is_index_current(sources: List[str]) -> bool:
    """Return True if the persisted index matches the current document sources."""
    if not all(os.path.exists(f) for f in [CHUNKS_FILE, EMBEDDINGS_FILE, FINGERPRINT_FILE]):
        return False
    with open(FINGERPRINT_FILE, "r") as f:
        stored = f.read().strip()
    return stored == _fingerprint(sources)


def load_index():
    """Load chunks and embeddings from disk. Returns (chunks, embeddings)."""
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    embeddings = np.load(EMBEDDINGS_FILE)
    return chunks, embeddings


def save_index(chunks: List[dict], embeddings: np.ndarray, sources: List[str]):
    """Persist chunks and embeddings to disk."""
    os.makedirs(STORE_DIR, exist_ok=True)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f)
    np.save(EMBEDDINGS_FILE, embeddings.astype(np.float32))
    with open(FINGERPRINT_FILE, "w") as f:
        f.write(_fingerprint(sources))


def cosine_search(query_vec: np.ndarray, embeddings: np.ndarray, top_k: int) -> List[int]:
    """Return indices of top_k most similar vectors using cosine similarity."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
    normed = embeddings / norms
    scores = normed @ q
    return list(np.argsort(scores)[::-1][:top_k]), scores
