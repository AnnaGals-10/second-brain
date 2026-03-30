import os
import re
import networkx as nx
from pathlib import Path
from openai import OpenAI

client = OpenAI()

def parse_links(content: str) -> list:
    return re.findall(r'\[\[([^\]]+)\]\]', content)

def build_graph(vault_path: str) -> nx.DiGraph:
    G = nx.DiGraph()
    vault = Path(vault_path)

    notes = {}
    for md_file in vault.glob("**/*.md"):
        name = md_file.stem
        content = md_file.read_text(encoding="utf-8")
        notes[name] = content
        G.add_node(name, content=content, path=str(md_file), has_note=True)

    for name, content in notes.items():
        for link in parse_links(content):
            if link not in G.nodes:
                G.add_node(link, content="", path="", has_note=False)
            G.add_edge(name, link)

    return G

def get_node_embedding(text: str) -> list:
    if not text.strip():
        return None
    response = client.embeddings.create(
        input=text[:2000],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def enrich_graph_with_embeddings(G: nx.DiGraph) -> nx.DiGraph:
    for node in G.nodes():
        content = G.nodes[node].get("content", "")
        if content:
            G.nodes[node]["embedding"] = get_node_embedding(content)
    return G

def get_graph_stats(G: nx.DiGraph) -> dict:
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "most_connected": sorted(G.degree(), key=lambda x: x[1], reverse=True)[:5],
    }
