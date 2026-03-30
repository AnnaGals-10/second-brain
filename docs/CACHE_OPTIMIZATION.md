# Query Cache & Token Optimization

Auto-reducción de tokens usando conversaciones importadas y deduplicación inteligente.

---

## How It Works

### **Flow 1: Conversaciones Importadas** (Hook + Watcher)

```
conversations.json (claude.ai o Code)
    ↓
import_conversations.py
    ↓ (auto-cachea Q&A pairs)
QueryCache (queries.json)
    ↓
graph_rag.py (busca exactas/similares)
    ↓
answered_query (0 tokens)
```

Cuando ejecutas:
```bash
python claude_code_hook.py
```

Cada conversación importada extrae pares de preguntas-respuestas y los guarda en `queries.json` para reutilización inmediata.

---

### **Flow 2: Preguntas en la App** (Streamlit)

```
Usuario pregunta en app
    ↓
answer_query(query, graph)
    ↓
check_exact_match()  → ¿pregunta idéntica? Sí → cached_answer (0 tokens)
    ↓
check_similar_query()  → ¿pregunta parecida? Sí → cached_answer (confidence score shown)
    ↓
graph_rag()  → No encontrado → pregunta a Claude
    ↓
cache_answer()  → guarda para futuro
    ↓
respuesta a usuario (con indicador de cache/tokens)
```

---

## Cache Storage

**Archivo:** `queries.json`

```json
{
  "3f4a5c2e9d1b4f8a": {
    "query": "How do I optimize Python performance?",
    "answer": "Use list comprehensions, NumPy vectorization...",
    "created_at": "2026-03-30T14:23:45.123456",
    "tokens_used": 150,
    "nodes_used": ["Python Performance Tips", "Optimization Patterns"],
    "embedding": [0.023, -0.015, 0.042, ...]
  }
}
```

**Clave:** Hash MD5 de la pregunta normalizada (exacto)  
**Embedding:** Para búsqueda semántica de preguntas similares

---

## Cómo Claude Lee El Markdown

### **Opción A: Conversaciones Importadas**

```python
# import_conversations.py → auto-caching
for msg_pair in conversation:
    question = msg_pair["user_message"]
    answer = msg_pair["claude_response"]
    cache.cache_answer(question, answer)  # ← Guarda en queries.json
```

### **Opción B: Preguntas de la App**

```python
# app.py → tab_chat
question = st.chat_input()  # usuario escribe
result = answer_query(G, question)  # ← chequea cache primero

if cached:
    return cached_answer  # ⚡ 0 tokens
else:
    send_to_claude()
    cache.cache_answer(question, response)  # ← guarda para próxima vez
```

---

## Ejemplos de Uso

### **Scenario 1: Pregunta Idéntica**

```
Usuario: "How do I install LangChain?"
    ↓
App chequea queries.json → "How do I install LangChain?" existe
    ↓
⚡ Exact Match — Respuesta instant (0 tokens)
    ↓
En chat: "⚡ Exact Match 0 tokens saved"
```

### **Scenario 2: Pregunta Similar**

```
Usuario: "What's the best Python library for vector search?"
    ↓
Sistema chequea queries.json:
  - "How to use FAISS for embeddings?" (similarity: 0.92)
  - "Vector search implementation?" (similarity: 0.88)
    ↓
App muestra la respuesta más similar con confidence
    ↓
En chat: "⚡ Similar Medium (similarity: 0.92)"
```

### **Scenario 3: Pregunta Nueva**

```
Usuario: "Explain quantum entanglement in simple terms"
    ↓
No hay match en cache
    ↓
Sistema: "Searching the graph..."
    ↓
Pregunta a Claude (usa contexto de vault)
    ↓
Claude responde (e.g., 240 tokens)
    ↓
cache.cache_answer() → guarda en queries.json
    ↓
Proxima pregunta similar → cached answer (0 tokens)
```

---

## Stats Dashboard (app.py)

**Tab "Ask" muestra:**

```
┌──────────────────┬──────────────┬─────────────────┐
│ Cached Queries   │ Tokens Saved │ Cache Size      │
├──────────────────┼──────────────┼─────────────────┤
│ 47               │ 8,320        │ 0.34 MB         │
└──────────────────┴──────────────┴─────────────────┘
```

Actualiza en tiempo real mientras usas la app.

---

## Performance Impact

### **Sin Cache**
- Pregunta 1: claudeAPI → 150 tokens
- Pregunta 2 (idéntica): claudeAPI → 150 tokens
- **Total: 300 tokens**

### **Con Cache (Option C)**
- Pregunta 1: claudeAPI → 150 tokens
- Pregunta 2 (idéntica): cache hit → 0 tokens
- Pregunta 3 (similar): cache hit → 0 tokens
- **Total: 150 tokens (50% reduction)**

Con conversaciones importadas, reduction es mucho mayor:
- Vault tiene 50 conversaciones × 5 Q&A pairs = 250 preguntas pre-cacheadas
- Si 30% de tus nuevas preguntas coinciden → ~75% tokens saved

---

## Configuration

### **Adjust Similarity Threshold**

En [query_cache.py](query_cache.py):

```python
SIMILARITY_THRESHOLD = 0.85  # 0-1
# 0.85 = strict (solo muy similares)
# 0.70 = loose (sugiere respuestas remotamente relacionadas)
# 0.95 = ultra-strict (solo matches casi idénticos)
```

### **Cache Location**

Default: `queries.json` en project root

Para cambiar:
```python
# app.py
cache = QueryCache(cache_file="/custom/path/queries.json")
```

### **Clear Cache**

```bash
# Desde Python
python -c "from query_cache import QueryCache; QueryCache().clear_cache()"

# O simplemente
rm queries.json
```

---

## Cost Savings Example

**Setup:**
- GPT-4o-mini: $0.15 per 1M input tokens
- Promedio pregunta: 150 tokens input

**Antes (sin cache):**
- 100 queries/mes × 150 tokens = 15,000 tokens = $0.00225

**Después (con cache):**
- 30 queries cache hit (0 tokens)
- 70 queries × 150 tokens = 10,500 tokens = $0.00158
- **Savings: 30% = $0.00067/mes**

Con usage real (1k+ queries/month):
- **Savings: $2-5/mes** con 30% hit rate
- **Savings: $10-20/mes** con 70% hit rate (high repetition, como estudios)

---

## Monitoring

View cache growth over time:

```bash
# Check cache file
ls -lh queries.json

# Count cached queries
python -c "import json; d=json.load(open('queries.json')); print(f'{len(d)} cached queries')"

# See recent most cached
python -c "
import json
import operator
queries = json.load(open('queries.json'))
by_tokens = sorted(queries.items(), key=lambda x: x[1]['tokens_used'], reverse=True)
for k, v in by_tokens[:5]:
    print(f\"{v['tokens_used']} tokens: {v['query'][:60]}...\")
"
```

---

## Flush-Clean

Cuando importe conversaciones nuevas, el hook aúto-cachea:

```bash
python claude_code_hook.py
# Importa 10 conversaciones nuevas
# Auto-cachea 47 preguntas nuevas
# +0.12 MB a queries.json
```

No necesitas hacer nada — automático.

---

## Limitations

- **Similarity threshold:** Queries muy específicas podrían no matchear aunque sean relacionadas
- **Embeddings cost:** Cada cache check requiere 1 embedding API call (~0.02 cents) — pero vale la pena si saves 100+ tokens
- **Stale answers:** Cache no se actualiza si la información en vault cambia. Para invalidar:
  ```python
  cache.clear_cache()  # Nuclear option, empieza fresh
  ```

---

## Future Enhancements

1. **Auto-expire old caches** — Borrar query answers después de 30 días
2. **Category-specific caches** — Separar por [Programming], [Science], [Personal]
3. **Feedback loop** — Marcar respuestas como "helpful" para boost similarity scoring
4. **Vector DB** — Migrar de JSON a Pinecone/Weaviate para queries 100k+

---

## Summary

✅ **Conversaciones importadas** → Auto-cacheadas, listas para reutilizar  
✅ **Preguntas de app** → Check cache primero, guarda respuestas nuevas  
✅ **UI feedback** → Indica si respuesta es del cache o de Claude  
✅ **Automatic** → Sin configuración manual requerida  

**Result:** Reutiliza conocimiento existente, reduce tokens innecesarios, economiza costos.
