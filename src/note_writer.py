import os
import re
from pathlib import Path
from openai import OpenAI

client = OpenAI()

def _slugify(name: str) -> str:
    return re.sub(r'[^\w\s\-]', '', name).strip()

def create_note(vault_path: str, title: str, content: str) -> str:
    """Write a new .md note to the vault."""
    vault = Path(vault_path)
    filename = _slugify(title) + ".md"
    path = vault / filename
    path.write_text(content, encoding="utf-8")
    return str(path)

def generate_note_with_ai(title: str, context: str = "", language: str = "English") -> str:
    """Generate a structured note using AI."""
    prompt = (
        f"Write a concise Obsidian-style note titled '{title}'. Reply in {language}.\n"
        "Format:\n"
        "- Start with # Title\n"
        "- 3-5 sentences of content\n"
        "- Use [[linked concept]] syntax to reference related topics\n"
        "- Be factual and knowledge-dense, no fluff\n\n"
        f"Additional context: {context}" if context else ""
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

def suggest_links(content: str, existing_notes: list) -> list:
    """Suggest existing notes that should be linked from this content."""
    notes_str = ", ".join(existing_notes[:50])
    prompt = (
        f"Given this note content:\n{content}\n\n"
        f"And these existing notes: {notes_str}\n\n"
        "Which existing notes should be linked with [[note name]] syntax? "
        "Return only a JSON array of note names that are genuinely relevant: "
        '["Note A", "Note B"]'
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    import json
    try:
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return []
