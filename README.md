# Second Brain — Knowledge Graph RAG with Auto-Import

Auto-import Claude conversations + build searchable knowledge graph with semantic caching.

---

## Directory Structure

```
second-brain/
├── src/                    # Core modules (importable as package)
│   ├── __init__.py
│   ├── app.py             # Streamlit web interface
│   ├── graph_builder.py   # Parse vault → NetworkX graph
│   ├── graph_rag.py       # RAG pipeline: query → search → Claude → cache
│   ├── query_cache.py     # Query deduplication + semantic similarity
│   ├── note_writer.py     # Create notes with AI
│   └── web_fetcher.py     # Import web content (URLs, RSS)
├── automation/            # Background scripts & hooks
│   ├── import_conversations.py  # Convert conversations.json → markdown
│   ├── claude_code_hook.py      # Session-based import
│   ├── watcher.py               # File monitor (Option B)
│   └── startup_watcher.py       # Watcher daemon launcher
├── data/                  # State files (git-ignored)
│   ├── queries.json       # Cached Q&A pairs (404 examples)
│   ├── .claude_code_state.json  # Hook state tracking
│   └── rss_feeds.json     # Web fetcher RSS list
├── config/                # Configuration
│   └── .env               # Environment variables
├── docs/                  # Documentation
│   └── CACHE_OPTIMIZATION.md
├── vault/                 # Your knowledge base (git-ignored)
│   ├── *.md               # General notes
│   └── conversations/     # Imported conversations
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up environment

Create `config/.env`:
```env
OPENAI_API_KEY=sk-...
VAULT_PATH=./vault
CONVERSATIONS_FILE=./conversations.json
```

### 3. Run the app

```bash
streamlit run src/app.py
```

The app starts with an empty knowledge graph. Import conversations to populate it.

---

## Import Methods

### Option A: Claude Code Session Hook

After closing a Code session, run:
```bash
python automation/claude_code_hook.py
```

**How it works:**
- Maintains state at `data/.claude_code_state.json`
- Detects new conversations since last run
- Converts JSON conversations to markdown (vault/conversations/)
- Auto-caches all Q&A pairs for semantic search

**Silent mode (for automation):**
```bash
python automation/claude_code_hook.py --auto
```

### Option B: File Watcher Daemon

Real-time monitoring of `conversations.json`:

**Start:**
```bash
python automation/startup_watcher.py
```

**For Windows (hidden process):**
```powershell
Start-Process python -ArgumentList "automation/startup_watcher.py" -WindowStyle Hidden
```

**For Linux/Mac (background):**
```bash
nohup python automation/startup_watcher.py > watcher.log 2>&1 &
```

How it works:
- Watches `conversations.json` for changes
- Debounces rapid modifications (5-second cooldown)
- Runs `automation/import_conversations.py` automatically
- No manual intervention needed

### Initial Cache Population

Load pre-existing conversations into cache:
```bash
python automation/initial_cache.py
```

This caches all Q&A pairs from current `conversations.json` without manual embedding generation (lazy mode).

---

## How It Works

### 1. Import (conversations.json → vault/)

```
conversations.json
    ↓ import_conversations.py
vault/conversations/*.md
    ↓ graph_builder.py (parse markdown)
Knowledge graph (NetworkX)
```

**What happens:**
- Each conversation → 1 markdown file
- Questions auto-cached to `data/queries.json`
- Embeddings generated lazily (on first query, saves API $)

### 2. Query (ask Streamlit app)

```
User question
    ↓ query_cache.py (check cache)
    ├─ Exact match? → Answer (0 tokens)
    └─ Similar query? → Answer (0 tokens)
    ↓ (if no match)
    ├─ graph_rag.py (semantic search)
    ├─ find_relevant_nodes (embeddings)
    ├─ build_context (top 3 relevant notes)
    ↓
    ├─ Claude API (answer with context)
    └─ cache_answer (store for future)
```

**Cache benefits:**
- **Exact match:** Instant, 0 tokens
- **Similar query (0.85+ similarity):** Instant, 0 tokens
- **New query:** Uses Claude, then cached forever
- **Result:** ~30-50% token reduction on repeat questions

### 3. Semantic Search

**Embeddings:**
- Generated on first query (lazy)
- Uses text-embedding-3-small (cheap: $0.02/M tokens)
- Cached at query level, not note level

**Graph search:**
- Finds top 3 most relevant notes via cosine similarity
- Builds context from matched notes
- Passes to Claude for final answer

---

## Web Import

Add articles from web to your vault:

```bash
# Single article
python -c "from src.web_fetcher import fetch_url; fetch_url('https://...')"

# Or via Streamlit app → Web tab
```

Features:
- Auto-summarize with Claude
- Suggest wikilinks to existing notes
- Save as markdown in vault/

---

## Cache Statistics

Check your cache stats:

```bash
python -c "from src.query_cache import QueryCache; print(QueryCache().get_stats())"
```

Example output:
```
{
  'total_cached_queries': 404,
  'cache_size_mb': 0.49,
  'cached_queries': [...]
}
```

---

## Configuration

### Environment Variables (config/.env)

```env
# OpenAI API key (required)
OPENAI_API_KEY=sk-proj-...

# Path to vault directory
VAULT_PATH=./vault

# Path to conversations.json export
CONVERSATIONS_FILE=./conversations.json
```

### Customize Import Format

Edit `automation/import_conversations.py`:
- `conversation_to_md()` — Change markdown format
- `slugify()` — Change filename generation
- Conversation filtering logic

### Adjust Cache Behavior

Edit `src/query_cache.py`:
- `SIMILARITY_THRESHOLD = 0.85` — Strictness of semantic matching
- `generate_embedding=False` in `cache_answer()` — Use lazy mode
- Cache location: `data/queries.json`

---

## Advanced Usage

### Bulk Import

Import all conversations once:
```bash
# Populate cache with existing conversations (no embedding generation)
python automation/initial_cache.py

# Then start app
streamlit run src/app.py
```

### Graph Visualization

In Streamlit app, "Graph" tab shows:
- All notes as nodes
- Wikilinks as edges
- Interactive PyVis visualization
- Click to explore connections

### Building Links

When you create notes or import web content, the app suggests wikilinks:
```
[[Existing Note]]
```

These automatically appear in the knowledge graph as connections.

---

## Troubleshooting

**File watcher not detecting changes:**
- Check: `pip list | grep watchdog`
- Ensure conversations.json exists and is readable
- Try manual import: `python automation/import_conversations.py conversations.json`

**Hook says "conversations.json not found":**
- Verify path in config/.env
- Check file exists: `ls -la conversations.json` (or `dir conversations.json` on Windows)

**Duplicate conversations being imported:**
- Delete `data/.claude_code_state.json` and re-run hook
- Or delete specific .md files in vault/conversations/

**Queries not being cached:**
- Check `data/queries.json` exists
- Verify write permissions: `ls -la data/`
- Run: `python -c "from src.query_cache import QueryCache; print(QueryCache().get_stats())"`

**Embeddings taking too long:**
- Expected on first query (~1-2s)
- Cached for future use
- Use lazy mode in `initial_cache.py` to avoid generating all at once

---

## Performance Tips

**Token optimization:**
1. Use query cache — questions asked before cost 0 tokens
2. Lazy embeddings — don't generate unless queried
3. Check cache stats: `python automation/initial_cache.py` shows cached count

**Speed optimization:**
1. Keep vault < 1000 notes (graph builds in <1s)
2. Run watcher on SSD for faster detection
3. Use `–no-cache` in Streamlit if having issues: `streamlit run src/app.py -- --no-cache`

**Storage:**
- `data/queries.json` grows with questions (1 entry per unique query)
- 404 cached pairs = 0.49 MB
- Periodically archive old conversations to keep vault lean

---

## Files Reference

| Path | Purpose |
|------|---------|
| `src/app.py` | Streamlit UI (graph, ask, create notes, web import) |
| `src/graph_builder.py` | Parse vault + build knowledge graph |
| `src/graph_rag.py` | Query interface + Claude integration |
| `src/query_cache.py` | Deduplication + semantic search |
| `src/note_writer.py` | Create/link notes with AI |
| `src/web_fetcher.py` | Import URLs + RSS feeds |
| `automation/import_conversations.py` | Convert conversations.json → markdown |
| `automation/claude_code_hook.py` | Post-Code-session importer |
| `automation/watcher.py` | File monitor (watchdog-based) |
| `automation/startup_watcher.py` | Watcher launcher |
| `automation/initial_cache.py` | Bulk cache population |
| `data/queries.json` | Cached Q&A (404 examples) |
| `data/.claude_code_state.json` | Hook state tracker |
| `data/rss_feeds.json` | Web fetcher feed list |
| `config/.env` | API key + paths |

---

## FAQ

**Q: Do I need both import methods?**  
A: No, choose one:
- **Option A** (hook) — Good for Code sessions, manual control
- **Option B** (watcher) — Good for web interface, fully automatic

**Q: Will conversations be duplicated?**  
A: No. Option A uses state tracking at `data/.claude_code_state.json`. Option B debounces. Both avoid dupes.

**Q: How much does this cost?**  
A: Mainly embeddings ($0.02/M tokens). Chat is cached after first query. Pre-caching conversations avoids tokens on import.

**Q: Can I search across all conversations?**  
A: Yes, graphs and semantic search work across all vault notes including imported conversations.

**Q: How do I export conversations from Claude?**  
A: Download `conversations.json` from claude.ai account settings → Data export

---

## Integration Examples

### Windows Task Scheduler (Run hook after Code closes)

```powershell
$scriptPath = "C:\path\to\second-brain\automation\claude_code_hook.py"
$trigger = New-ScheduledTaskTrigger -AtLogOff
$action = New-ScheduledTaskAction -Execute "python" -Argument $scriptPath -WorkingDirectory $(Split-Path $scriptPath)
Register-ScheduledTask -TaskName "Claude Code Importer" -Trigger $trigger -Action $action
```

### Linux/Mac (Add to shell profile)

```bash
# ~/.bashrc or ~/.zshrc
alias claude-sync="python /path/to/second-brain/automation/claude_code_hook.py"
alias second-brain="streamlit run /path/to/second-brain/src/app.py"
```

---

## Next Steps

1. **Install:** `pip install -r requirements.txt`
2. **Configure:** Create `config/.env` with API key
3. **Import:** Run `python automation/claude_code_hook.py` or start Option B watcher
4. **Explore:** `streamlit run src/app.py` → Graph tab to see vault
5. **Query:** Ask questions in "Ask" tab → watch cache fill up
6. **Create:** Add new notes/web content → watch knowledge graph grow

---

*Built for semantic search + cost optimization over repeated questions.*
