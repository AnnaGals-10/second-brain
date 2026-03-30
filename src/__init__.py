"""
Second Brain - Knowledge Graph RAG System

Core modules for building and querying a semantic knowledge base.
"""

__version__ = "1.0.0"

# Make modules importable from src package
try:
    from .graph_builder import build_graph, enrich_graph_with_embeddings, get_graph_stats
    from .graph_rag import answer_query, find_relevant_nodes, build_context
    from .query_cache import QueryCache
    from .note_writer import create_note, generate_note_with_ai, suggest_links
    from .web_fetcher import fetch_url, summarize_and_link
except ImportError:
    from graph_builder import build_graph, enrich_graph_with_embeddings, get_graph_stats
    from graph_rag import answer_query, find_relevant_nodes, build_context
    from query_cache import QueryCache
    from note_writer import create_note, generate_note_with_ai, suggest_links
    from web_fetcher import fetch_url, summarize_and_link

__all__ = [
    "build_graph",
    "enrich_graph_with_embeddings", 
    "get_graph_stats",
    "answer_query",
    "find_relevant_nodes",
    "build_context",
    "QueryCache",
    "create_note",
    "generate_note_with_ai",
    "suggest_links",
    "fetch_url",
    "summarize_and_link",
]
