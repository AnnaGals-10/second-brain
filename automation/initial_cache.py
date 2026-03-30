#!/usr/bin/env python3
"""
Initial caching of all existing conversations.
Run this once to populate queries.json from conversations.json
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

from query_cache import QueryCache

CONVERSATIONS_FILE = os.getenv("CONVERSATIONS_FILE", "conversations.json")

print("Caching all conversations...")

with open(CONVERSATIONS_FILE, encoding="utf-8") as f:
    conversations = json.load(f)

cache = QueryCache()
total_cached = 0

for conv in conversations:
    messages = conv.get("chat_messages", [])
    conv_name = conv.get("name", "Untitled")
    
    for i in range(0, len(messages) - 1, 2):
        if messages[i].get("sender") == "human" and i + 1 < len(messages):
            if messages[i + 1].get("sender") != "human":
                question = messages[i].get("text", "").strip()
                answer = messages[i + 1].get("text", "").strip()
                
                if question and answer and len(question) > 10:
                    try:
                        cache.cache_answer(
                            query=question,
                            answer=answer,
                            tokens_used=0,
                            nodes_used=[conv_name],
                            generate_embedding=False
                        )
                        total_cached += 1
                    except Exception as e:
                        print(f"  ⚠ Error: {e}")

print(f"✓ Cached {total_cached} Q&A pairs from {len(conversations)} conversations")

# Show stats
stats = cache.get_stats()
print(f"\nCache stats:")
print(f"  Total queries: {stats['total_cached_queries']}")
print(f"  Cache size: {stats['cache_size_mb']:.2f} MB")
