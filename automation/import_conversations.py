#!/usr/bin/env python3
"""
Converts conversations.json (Claude export) into .md notes in the vault.
Each conversation becomes one note with full dialogue.
Auto-caches conversations for query deduplication.
"""
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Add src/ to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from query_cache import QueryCache

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

CONVERSATIONS_FILE = os.getenv("CONVERSATIONS_FILE", "conversations.json")
VAULT_PATH = os.getenv("VAULT_PATH", "./vault")

def slugify(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:80]

def format_message(msg: dict) -> str:
    sender = msg.get("sender", "unknown")
    text   = msg.get("text", "").strip()
    if not text:
        return ""
    role = "**You**" if sender == "human" else "**Claude**"
    return f"{role}\n{text}"

def conversation_to_md(conv: dict) -> tuple[str, str]:
    """Returns (filename, markdown_content)"""
    name     = conv.get("name") or "Untitled"
    summary  = conv.get("summary", "")
    created  = conv.get("created_at", "")[:10]
    messages = conv.get("chat_messages", [])

    # Build markdown
    lines = [f"# {name}", ""]

    if created:
        lines += [f"> Created: {created}", ""]

    if summary:
        # Keep only first paragraph of summary
        first_para = summary.strip().split("\n\n")[0]
        first_para = re.sub(r'\*\*[^*]+\*\*\n?', '', first_para).strip()
        if first_para:
            lines += ["## Summary", first_para, ""]

    lines.append("## Conversation")
    lines.append("")

    for msg in messages:
        formatted = format_message(msg)
        if formatted:
            lines.append(formatted)
            lines.append("")

    filename = f"{created} {slugify(name)}" if created else slugify(name)
    return filename, "\n".join(lines)

def import_all(conversations_file: str = CONVERSATIONS_FILE,
               vault_path: str = VAULT_PATH) -> list[str]:
    vault = Path(vault_path)
    chats_dir = vault / "conversations"
    chats_dir.mkdir(parents=True, exist_ok=True)

    with open(conversations_file, encoding="utf-8") as f:
        data = json.load(f)

    cache = QueryCache()
    created_files = []
    questions_cached = 0
    
    for conv in data:
        filename, content = conversation_to_md(conv)
        path = chats_dir / f"{filename}.md"
        path.write_text(content, encoding="utf-8")
        created_files.append(str(path))
        print(f"  OK {filename}.md")
        
        # Auto-cache each conversation's Q&A pairs
        messages = conv.get("chat_messages", [])
        for i in range(0, len(messages) - 1, 2):
            if messages[i].get("sender") == "human" and i + 1 < len(messages) and messages[i + 1].get("sender") != "human":
                question = messages[i].get("text", "").strip()
                answer = messages[i + 1].get("text", "").strip()
                
                if question and answer and len(question) > 10:  # Only cache meaningful questions
                    try:
                        cache.cache_answer(
                            query=question,
                            answer=answer,
                            tokens_used=0,
                            nodes_used=[filename]
                        )
                        questions_cached += 1
                    except Exception as e:
                        print(f"  ⚠ Failed to cache: {e}")

    print(f"\n✓ {len(created_files)} conversations imported")
    print(f"✓ {questions_cached} Q&A pairs cached")
    return created_files

if __name__ == "__main__":
    conv_file = sys.argv[1] if len(sys.argv) > 1 else CONVERSATIONS_FILE
    print(f"Importing conversations to {VAULT_PATH}/conversations/...")
    files = import_all(conversations_file=conv_file)
    print(f"\nDone — {len(files)} notes created.")
