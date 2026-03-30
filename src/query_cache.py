"""
Query cache and deduplication for second-brain.

Before sending a query to Claude, checks:
1. Has this question been asked before? If yes, return cached answer (0 tokens)
2. Is there a similar existing answer in vault? If yes, suggest it
3. If new, send to Claude and cache the answer

Cache structure (queries.json):
{
  "query_hash": {
    "query": "original question",
    "answer": "claude's response",
    "created_at": "ISO timestamp",
    "nodes_used": ["note1", "note2"],
    "tokens_used": 150,
    "embedding": [...]
  }
}
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
from openai import OpenAI

client = OpenAI()

# Cache file in data/ directory
DATA_PATH = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_PATH / "queries.json"
SIMILARITY_THRESHOLD = 0.85  # 0-1, higher = more similar


class QueryCache:
    def __init__(self, cache_file: Path = None):
        if cache_file is None:
            cache_file = CACHE_FILE
        self.cache_path = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load existing cache or initialize empty."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _get_query_hash(self, query: str) -> str:
        """Get deterministic hash of query (for exact matches)."""
        normalized = query.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_embedding(self, text: str) -> list:
        """Get embeddings from OpenAI."""
        response = client.embeddings.create(
            input=text[:2000],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    def _cosine_similarity(self, a: list, b: list) -> float:
        """Calculate cosine similarity between two embeddings."""
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

    def get_exact_match(self, query: str) -> Optional[dict]:
        """Check if exact query already exists in cache."""
        query_hash = self._get_query_hash(query)
        if query_hash in self.cache:
            entry = self.cache[query_hash]
            return {
                "type": "exact_match",
                "answer": entry["answer"],
                "created_at": entry["created_at"],
                "tokens_saved": entry.get("tokens_used", 0),
            }
        return None

    def get_similar_query(self, query: str) -> Optional[dict]:
        """Find similar queries in cache using semantic similarity."""
        if not self.cache:
            return None

        query_emb = self._get_embedding(query)
        best_match = None
        best_score = 0
        embeddings_updated = False

        for query_hash, entry in self.cache.items():
            cached_emb = entry.get("embedding")
            
            # Generate embedding lazily if not present
            if not cached_emb:
                try:
                    cached_emb = self._get_embedding(entry["query"])
                    entry["embedding"] = cached_emb
                    embeddings_updated = True
                except Exception:
                    continue
            
            if not cached_emb:
                continue

            score = self._cosine_similarity(query_emb, cached_emb)
            if score > best_score:
                best_score = score
                best_match = (entry, score)

        # Save embeddings if we generated new ones
        if embeddings_updated:
            self._save_cache()

        if best_match and best_score >= SIMILARITY_THRESHOLD:
            entry, score = best_match
            return {
                "type": "similar",
                "similarity_score": round(score, 3),
                "original_query": entry["query"],
                "answer": entry["answer"],
                "created_at": entry["created_at"],
                "confidence": "high" if score > 0.95 else "medium",
            }

        return None

    def cache_answer(self, query: str, answer: str, 
                     tokens_used: int = 0, 
                     nodes_used: list = None,
                     generate_embedding: bool = False) -> str:
        """
        Store query and answer in cache.
        
        Args:
            query: The question
            answer: The answer
            tokens_used: Tokens consumed from API (0 for imported answers)
            nodes_used: List of source notes
            generate_embedding: If True, generate embedding now. If False, defer until first query.
        """
        query_hash = self._get_query_hash(query)
        
        embedding = None
        if generate_embedding:
            embedding = self._get_embedding(query)
        
        entry = {
            "query": query,
            "answer": answer,
            "created_at": datetime.now().isoformat(),
            "tokens_used": tokens_used,
            "nodes_used": nodes_used or [],
            "embedding": embedding,  # None until first use
        }
        
        self.cache[query_hash] = entry
        self._save_cache()
        return query_hash

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.cache:
            return {
                "total_cached_queries": 0,
                "total_tokens_saved": 0,
                "cache_size_mb": 0,
            }

        total_tokens = sum(
            entry.get("tokens_used", 0)
            for entry in self.cache.values()
        )
        cache_size = self.cache_path.stat().st_size / (1024 * 1024) if self.cache_path.exists() else 0

        return {
            "total_cached_queries": len(self.cache),
            "total_tokens_saved": total_tokens,
            "cache_size_mb": round(cache_size, 2),
        }

    def clear_cache(self):
        """Clear entire cache."""
        self.cache = {}
        self._save_cache()


def check_cache_before_query(query: str) -> Optional[dict]:
    """
    Check cache before sending query to Claude.
    Returns cached answer if found, None otherwise.
    """
    cache = QueryCache()
    
    # Try exact match first (fastest)
    exact = cache.get_exact_match(query)
    if exact:
        return exact

    # Try semantic similarity (slower but finds related answers)
    similar = cache.get_similar_query(query)
    if similar:
        return similar

    return None
