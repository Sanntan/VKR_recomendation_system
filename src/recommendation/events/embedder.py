from __future__ import annotations
from typing import Optional, List

_DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

class TextEmbedder:
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name or _DEFAULT_MODEL)

    def encode_one(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        vec = self.model.encode(text, normalize_embeddings=True)
        return vec.astype(float).tolist()
