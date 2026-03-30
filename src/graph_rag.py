import numpy as np
import networkx as nx
from openai import OpenAI

try:
    from .query_cache import QueryCache
except ImportError:
    from query_cache import QueryCache

client = OpenAI()

def _cosine_similarity(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

def _get_embedding(text: str) -> list:
    response = client.embeddings.create(
        input=text[:2000],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def find_relevant_nodes(G: nx.DiGraph, query: str, top_k: int = 5) -> list:
    """Find the most semantically relevant nodes for a query."""
    query_emb = _get_embedding(query)
    scored = []
    for node in G.nodes():
        emb = G.nodes[node].get("embedding")
        if emb:
            score = _cosine_similarity(query_emb, emb)
            scored.append((node, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

def expand_context(G: nx.DiGraph, nodes: list) -> list:
    """Expand context by including direct neighbours of relevant nodes."""
    expanded = set(n for n, _ in nodes)
    for node, _ in nodes:
        expanded.update(G.predecessors(node))
        expanded.update(G.successors(node))
    return list(expanded)

def build_context(G: nx.DiGraph, nodes: list) -> str:
    parts = []
    for node in nodes:
        content = G.nodes[node].get("content", "")
        if content:
            links = list(G.successors(node))
            links_str = ", ".join(f"[[{l}]]" for l in links) if links else "none"
            parts.append(f"## {node}\n{content.strip()}\nLinks to: {links_str}")
    return "\n\n".join(parts)

def answer_query(G: nx.DiGraph, query: str, language: str = "English") -> dict:
    """
    Answer a query using graph RAG with cache.
    
    Checks cache first:
    1. Exact match → return immediately (0 tokens)
    2. Similar query → return with similarity score
    3. New query → fetch from Claude, cache answer
    """
    cache = QueryCache()
    
    # Check cache first
    cached = cache.get_exact_match(query)
    if cached:
        return {
            "answer": cached["answer"],
            "nodes_used": [],
            "context": "",
            "cached": True,
            "cache_type": "exact_match",
            "tokens_saved": cached.get("tokens_saved", 0),
        }
    
    # Check for similar queries
    similar = cache.get_similar_query(query)
    if similar:
        return {
            "answer": similar["answer"],
            "nodes_used": [],
            "context": "",
            "cached": True,
            "cache_type": f"similar_{similar['confidence']}",
            "similarity_score": similar["similarity_score"],
            "original_query": similar["original_query"],
            "tokens_saved": similar.get("tokens_used", 0),
        }
    
    # Not in cache, proceed with graph RAG
    relevant = find_relevant_nodes(G, query, top_k=5)
    if not relevant:
        return {"answer": "No relevant nodes found.", "nodes_used": [], "context": "", "cached": False}

    expanded_nodes = expand_context(G, relevant)
    context = build_context(G, expanded_nodes)

    prompt = (
        f"You are a knowledgeable assistant. Reply in {language}.\n"
        "Answer the question based on the following knowledge graph context.\n"
        "Reference specific notes by name when relevant.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    answer = response.choices[0].message.content
    nodes_list = [n for n, _ in relevant]
    
    # Cache this new answer for future use
    cache.cache_answer(
        query=query,
        answer=answer,
        tokens_used=response.usage.completion_tokens if hasattr(response, 'usage') else 0,
        nodes_used=nodes_list
    )

    return {
        "answer": answer,
        "nodes_used": nodes_list,
        "context": context,
        "cached": False,
    }
