"""A minimal local vector store.

Deliberately avoids a hosted vector DB — everything runs on-disk with
FAISS + a local sentence-transformers model, so the project needs zero
extra infra or API keys to demo the RAG half of the agent.
"""
import json
import os
import threading

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "index")
INDEX_PATH = os.path.join(INDEX_DIR, "docs.faiss")
META_PATH = os.path.join(INDEX_DIR, "docs_meta.json")

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384
CHUNK_SIZE = 800  # characters
CHUNK_OVERLAP = 150


def chunk_text(text: str, source: str) -> list[dict]:
    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({"text": chunk, "source": source})
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


class VectorStore:
    """Thread-safe wrapper around a flat FAISS index + JSON metadata sidecar."""

    def __init__(self):
        self._lock = threading.Lock()
        self._model = None  # lazy-loaded, first call pays the cost
        os.makedirs(INDEX_DIR, exist_ok=True)
        if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            with open(META_PATH) as f:
                self.metadata: list[dict] = json.load(f)
        else:
            self.index = faiss.IndexFlatIP(EMBED_DIM)
            self.metadata = []

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(EMBED_MODEL_NAME)
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype="float32")

    def add_document(self, text: str, source: str) -> int:
        chunks = chunk_text(text, source)
        if not chunks:
            return 0
        vecs = self._embed([c["text"] for c in chunks])
        with self._lock:
            self.index.add(vecs)
            self.metadata.extend(chunks)
            self._persist()
        return len(chunks)

    def search(self, query: str, k: int = 4) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        qvec = self._embed([query])
        scores, idxs = self.index.search(qvec, min(k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            meta = self.metadata[idx]
            results.append(
                {"text": meta["text"], "source": meta["source"], "score": float(score)}
            )
        return results

    def stats(self) -> dict:
        sources = sorted({m["source"] for m in self.metadata})
        return {"chunks": len(self.metadata), "documents": sources}

    def _persist(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(META_PATH, "w") as f:
            json.dump(self.metadata, f)


# Single process-wide instance — fine for a demo/single-worker deployment.
store = VectorStore()
