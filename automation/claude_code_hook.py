#!/usr/bin/env python3
"""
Claude Code Session Hook

Runs when you close a Code session. Detects new conversations and auto-imports them.
Maintains a state file to track which conversations have been imported.

Usage:
  python claude_code_hook.py [--auto]
"""
import sys
import json
import hashlib
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

CONVERSATIONS_FILE = os.getenv("CONVERSATIONS_FILE", "conversations.json")
VAULT_PATH = os.getenv("VAULT_PATH", "./vault")
STATE_FILE = Path(__file__).parent.parent / "data" / ".claude_code_state.json"

from import_conversations import conversation_to_md
from query_cache import QueryCache


class CodeSessionHook:
    def __init__(self, conversations_file: str = CONVERSATIONS_FILE,
                 state_file: Path = STATE_FILE,
                 vault_path: str = VAULT_PATH):
        self.conv_file = Path(conversations_file)
        self.state_file = Path(state_file)
        self.vault_path = Path(vault_path)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load previous state or initialize new one."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                return {"imported_ids": [], "last_run": None}
        return {"imported_ids": [], "last_run": None}

    def _save_state(self):
        """Save current state to file."""
        self.state["last_run"] = datetime.now().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.state, indent=2),
            encoding="utf-8"
        )

    def _get_conv_id(self, conv: dict) -> str:
        """Generate a unique ID for a conversation."""
        name = conv.get("name", "")
        created = conv.get("created_at", "")
        signature = f"{name}:{created}"
        return hashlib.md5(signature.encode()).hexdigest()

    def run(self, verbose: bool = True) -> list[str]:
        """Check for new conversations and import them."""
        if not self.conv_file.exists():
            if verbose:
                print(f"[Code Hook] {self.conv_file} not found")
            return []

        try:
            conversations = json.loads(
                self.conv_file.read_text(encoding="utf-8")
            )
        except Exception as e:
            if verbose:
                print(f"[Code Hook] Error reading {self.conv_file}: {e}")
            return []

        new_files = []
        chats_dir = self.vault_path / "conversations"
        chats_dir.mkdir(parents=True, exist_ok=True)

        cache = QueryCache()

        for conv in conversations:
            conv_id = self._get_conv_id(conv)
            
            if conv_id in self.state["imported_ids"]:
                continue

            try:
                filename, content = conversation_to_md(conv)
                path = chats_dir / f"{filename}.md"
                path.write_text(content, encoding="utf-8")
                self.state["imported_ids"].append(conv_id)
                new_files.append(str(path))
                if verbose:
                    print(f"[Code Hook] + {filename}.md")
                
                # Auto-cache Q&A pairs
                messages = conv.get("chat_messages", [])
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
                                        nodes_used=[filename]
                                    )
                                except Exception:
                                    pass
            except Exception as e:
                if verbose:
                    print(f"[Code Hook] Failed to import {conv.get('name')}: {e}")

        self._save_state()

        if verbose and new_files:
            print(f"[Code Hook] Imported {len(new_files)} new conversation(s)")

        return new_files


def main():
    verbose = "--auto" not in sys.argv
    hook = CodeSessionHook()
    new_files = hook.run(verbose=verbose)

    if not verbose:
        sys.exit(0 if new_files or not hook.conv_file.exists() else 1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
