import streamlit as st
import os, sys, json
from pathlib import Path

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "config" / ".env")

from graph_builder import build_graph, enrich_graph_with_embeddings, get_graph_stats
from graph_rag import answer_query
from query_cache import QueryCache
from note_writer import create_note, generate_note_with_ai, suggest_links
from web_fetcher import (import_url, import_batch, load_feeds, save_feeds,
                         fetch_rss, sync_rss_feed)

# Vault path - use absolute path from project root
VAULT_PATH_ENV = os.getenv("VAULT_PATH", "./vault")
if VAULT_PATH_ENV.startswith("./"):
    # Relative path: resolve from project root
    VAULT_PATH = Path(__file__).parent.parent / VAULT_PATH_ENV.lstrip("./")
else:
    # Absolute path
    VAULT_PATH = Path(VAULT_PATH_ENV)

VAULT_PATH = str(VAULT_PATH.resolve())  # Convert to absolute string path

st.set_page_config(page_title="Second Brain", page_icon="◈",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Session state ─────────────────────────────────────────────────────────────
for key, val in [("graph", None), ("chat", []), ("selected_node", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500&family=DM+Serif+Display:ital@0;1&display=swap');

*, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; background:#080808; color:#ede9e1; }
.block-container { padding:2.5rem 3rem 4rem; max-width:1400px; }
#MainMenu, footer, header { visibility:hidden; }

.nav { display:flex; justify-content:space-between; align-items:center;
       padding-bottom:2rem; border-bottom:1px solid #161616; margin-bottom:2.5rem; }
.nav-logo { font-family:'DM Serif Display',serif; font-size:1.35rem; color:#ede9e1; letter-spacing:-0.5px; }
.nav-logo span { color:#a89f8c; font-style:italic; }
.nav-tag { font-size:0.7rem; letter-spacing:2.5px; text-transform:uppercase; color:#3a3a3a; }

.div { border:none; border-top:1px solid #161616; margin:2rem 0; }
.lbl { font-size:0.78rem; font-weight:500; letter-spacing:2.5px; text-transform:uppercase; color:#5a5a5a; margin-bottom:1.25rem; }

.stat-card { padding:1.25rem 0; border-bottom:1px solid #161616; }
.stat-n { font-family:'DM Serif Display',serif; font-size:2.8rem; color:#ede9e1; line-height:1; }
.stat-lbl { font-size:0.7rem; letter-spacing:2px; text-transform:uppercase; color:#3a3a3a; margin-top:4px; }

.node-card { padding:1rem 1.25rem; background:#0d0d0d; border:1px solid #1a1a1a;
             border-radius:2px; margin-bottom:8px; cursor:pointer; }
.node-card:hover { border-color:#a89f8c; }
.node-title { font-size:0.9rem; font-weight:500; color:#ede9e1; margin-bottom:4px; }
.node-meta { font-size:0.72rem; color:#3a3a3a; }

.chat-user { text-align:right; margin:0.6rem 0; }
.chat-user p { display:inline-block; background:#131313; border:1px solid #222;
                border-radius:2px; padding:0.6rem 1rem; font-size:0.85rem; color:#ede9e1; max-width:75%; text-align:left; }
.chat-ai { text-align:left; margin:0.6rem 0; }
.chat-ai p { display:inline-block; background:#0a0a0a; border:1px solid #161616;
              border-radius:2px; padding:0.6rem 1rem; font-size:0.85rem; color:#a89f8c; line-height:1.65; max-width:85%; }

.note-preview { background:#0a0a0a; border:1px solid #1a1a1a; border-radius:2px;
                padding:1.25rem; font-size:0.85rem; color:#7a7a7a; line-height:1.7;
                font-family:monospace; white-space:pre-wrap; max-height:300px; overflow-y:auto; }
.link-tag { display:inline-block; background:#0f0f0f; border:1px solid #1e1e1e;
            border-radius:2px; padding:2px 10px; font-size:0.72rem; color:#a89f8c;
            margin:2px; }

.stButton > button { background:#0a0a0a; border:1px solid #222; color:#a89f8c;
    font-size:0.72rem; letter-spacing:1.5px; text-transform:uppercase;
    padding:0.45rem 1.1rem; border-radius:2px; font-family:'DM Sans',sans-serif; }
.stButton > button:hover { border-color:#a89f8c; }

[data-testid="stTabs"] button { font-size:0.72rem; letter-spacing:1.5px; text-transform:uppercase; color:#3a3a3a; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#ede9e1; border-bottom-color:#a89f8c; }

.stTextInput input, .stTextArea textarea {
    background:#0a0a0a !important; border:1px solid #1e1e1e !important;
    color:#ede9e1 !important; border-radius:2px !important; font-family:'DM Sans',sans-serif !important; }
.stProgress > div > div > div > div { background:#a89f8c !important; }
.stProgress > div > div > div { background:#161616 !important; }
</style>
""", unsafe_allow_html=True)

# ── Nav ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="nav">
  <div class="nav-logo">Second <span>Brain</span></div>
  <div class="nav-tag">Knowledge Graph</div>
</div>
""", unsafe_allow_html=True)

# ── Load graph ────────────────────────────────────────────────────────────────
vault = Path(VAULT_PATH)
notes_exist = list(vault.glob("**/*.md"))

col_load, col_info = st.columns([2, 3], gap="large")

with col_load:
    st.markdown('<div class="lbl">Vault</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.85rem;color:#5a5a5a;margin-bottom:1rem;">{os.path.abspath(VAULT_PATH)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.82rem;color:#3a3a3a;margin-bottom:1.5rem;">{len(notes_exist)} notes found</div>', unsafe_allow_html=True)

    build_btn = st.button("Build Knowledge Graph")
    if build_btn:
        with st.spinner(""):
            prog = st.progress(0, text="Parsing notes and links...")
            G = build_graph(VAULT_PATH)
            prog.progress(40, text="Generating embeddings...")
            G = enrich_graph_with_embeddings(G)
            prog.progress(100, text="Graph ready.")
            prog.empty()
            st.session_state.graph = G
            st.session_state.chat = []

with col_info:
    if st.session_state.graph:
        G = st.session_state.graph
        stats = get_graph_stats(G)
        st.markdown(f"""
        <div class="lbl">Graph stats</div>
        <div style="display:flex;gap:3rem;">
          <div class="stat-card"><div class="stat-n">{stats["nodes"]}</div><div class="stat-lbl">Nodes</div></div>
          <div class="stat-card"><div class="stat-n">{stats["edges"]}</div><div class="stat-lbl">Connections</div></div>
          <div class="stat-card"><div class="stat-n">{len(notes_exist)}</div><div class="stat-lbl">Notes</div></div>
        </div>
        """, unsafe_allow_html=True)

if not st.session_state.graph:
    st.markdown("""
    <hr class="div">
    <div style="padding:4rem 0;text-align:center;">
      <div style="font-family:'DM Serif Display',serif;font-size:2.5rem;color:#1e1e1e;letter-spacing:-1px;">
        Build the graph to begin.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

G = st.session_state.graph

st.markdown('<hr class="div">', unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_graph, tab_chat, tab_notes, tab_web = st.tabs(["Graph", "Ask", "New note", "Web"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GRAPH
# ═══════════════════════════════════════════════════════════════════════════════
with tab_graph:
    from pyvis.network import Network
    import streamlit.components.v1 as components

    col_vis, col_detail = st.columns([3, 1], gap="large")

    with col_vis:
        st.markdown('<div class="lbl">Interactive graph</div>', unsafe_allow_html=True)

        net = Network(height="580px", width="100%", bgcolor="#080808",
                      font_color="#ede9e1", directed=True)
        net.barnes_hut(gravity=-8000, central_gravity=0.3,
                       spring_length=120, spring_strength=0.05)

        for node in G.nodes():
            has_note = G.nodes[node].get("has_note", False)
            degree   = G.degree(node)
            size     = 12 + degree * 4
            color    = "#a89f8c" if has_note else "#2a2a2a"
            border   = "#ede9e1" if has_note else "#3a3a3a"
            net.add_node(node, label=node, size=size, color={"background": color, "border": border},
                         font={"size": 13, "color": "#ede9e1"},
                         title=f"{node}\n{degree} connections")

        for src, dst in G.edges():
            net.add_edge(src, dst, color="#2a2a2a", arrows="to", width=1)

        net.set_options("""
        {
          "edges": {"smooth": {"type": "continuous"}},
          "interaction": {"hover": true, "navigationButtons": false},
          "physics": {"stabilization": {"iterations": 150}}
        }
        """)

        html = net.generate_html()
        components.html(html, height=600, scrolling=False)

    with col_detail:
        st.markdown('<div class="lbl">Most connected</div>', unsafe_allow_html=True)
        stats = get_graph_stats(G)
        for node, degree in stats["most_connected"]:
            has_note = G.nodes[node].get("has_note", False)
            content  = G.nodes[node].get("content", "")
            preview  = content[:120].replace("\n", " ") + "..." if len(content) > 120 else content
            links    = list(G.successors(node))
            st.markdown(f"""
            <div class="node-card">
              <div class="node-title">{node}</div>
              <div class="node-meta">{degree} connections · {"note" if has_note else "referenced"}</div>
              {"" if not preview else f'<div style="font-size:0.78rem;color:#3a3a3a;margin-top:6px;">{preview}</div>'}
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="lbl" style="margin-top:2rem;">All notes</div>', unsafe_allow_html=True)
        for node in sorted(G.nodes()):
            if G.nodes[node].get("has_note"):
                links_out = list(G.successors(node))
                st.markdown(f"""
                <div class="node-card">
                  <div class="node-title">{node}</div>
                  <div class="node-meta">{len(links_out)} links out</div>
                </div>
                """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ASK
# ═══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("""
    <div style="margin-bottom:2rem;">
      <div style="font-family:'DM Serif Display',serif;font-size:2rem;color:#ede9e1;letter-spacing:-0.5px;">
        Ask your <em style="color:#a89f8c;">knowledge.</em>
      </div>
      <div style="font-size:0.88rem;color:#3a3a3a;margin-top:0.5rem;font-weight:300;">
        Questions answered using your notes as context. Repeated questions use cached answers to save tokens.
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Cache stats
    cache = QueryCache()
    cache_stats = cache.get_stats()
    if cache_stats["total_cached_queries"] > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cached Queries", cache_stats["total_cached_queries"])
        with col2:
            st.metric("Tokens Saved", cache_stats["total_tokens_saved"])
        with col3:
            st.metric("Cache Size", f"{cache_stats['cache_size_mb']:.2f} MB")

    for msg in st.session_state.chat:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user"><p>{msg["content"]}</p></div>', unsafe_allow_html=True)
        else:
            # Show cache indicator if applicable
            cache_info = ""
            if msg.get("cached"):
                cache_type = msg.get("cache_type", "").replace("_", " ").title()
                tokens_saved = msg.get("tokens_saved", 0)
                cache_info = f'<div style="font-size:0.72rem;color:#a89f8c;margin-bottom:0.5rem;letter-spacing:1px;">⚡ {cache_type} {tokens_saved} tokens saved' if tokens_saved else f'<div style="font-size:0.72rem;color:#a89f8c;margin-bottom:0.5rem;letter-spacing:1px;">⚡ {cache_type}'
                if msg.get("similarity_score"):
                    cache_info += f' (similarity: {msg["similarity_score"]})'
                cache_info += '</div>'
            
            st.markdown(f'<div class="chat-ai"><p>{msg["content"]}</p></div>', unsafe_allow_html=True)
            
            if cache_info:
                st.markdown(cache_info, unsafe_allow_html=True)
            
            if msg.get("nodes"):
                nodes_html = "".join(f'<span class="link-tag">{n}</span>' for n in msg["nodes"])
                st.markdown(f'<div style="margin-bottom:0.75rem;padding-left:4px;">{nodes_html}</div>',
                            unsafe_allow_html=True)

    question = st.chat_input("What do you want to know?")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.spinner("Searching the graph..."):
            result = answer_query(G, question)
        
        # Store cache info in message
        msg = {
            "role": "assistant",
            "content": result["answer"],
            "nodes": result.get("nodes_used", []),
            "cached": result.get("cached", False),
            "cache_type": result.get("cache_type"),
            "tokens_saved": result.get("tokens_saved", 0),
            "similarity_score": result.get("similarity_score"),
        }
        st.session_state.chat.append(msg)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — NEW NOTE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_notes:
    st.markdown("""
    <div style="margin-bottom:2rem;">
      <div style="font-family:'DM Serif Display',serif;font-size:2rem;color:#ede9e1;letter-spacing:-0.5px;">
        Add to your <em style="color:#a89f8c;">brain.</em>
      </div>
    </div>
    """, unsafe_allow_html=True)

    n1, n2 = st.columns(2, gap="large")

    with n1:
        st.markdown('<div class="lbl">Note title</div>', unsafe_allow_html=True)
        note_title = st.text_input("Title", label_visibility="collapsed",
                                   placeholder="e.g. LangGraph")

        st.markdown('<div class="lbl" style="margin-top:1.5rem;">Content</div>', unsafe_allow_html=True)
        note_content = st.text_area("Content", height=200, label_visibility="collapsed",
                                    placeholder="Write your note here, or generate it with AI...")

        c1, c2 = st.columns(2)
        with c1:
            gen_btn = st.button("Generate with AI")
        with c2:
            save_btn = st.button("Save note")

        if gen_btn and note_title:
            with st.spinner("Generating..."):
                generated = generate_note_with_ai(note_title)
            note_content = generated
            st.session_state["draft_content"] = generated
            st.rerun()

        if "draft_content" in st.session_state and not note_content:
            note_content = st.session_state["draft_content"]

        if save_btn and note_title and note_content:
            path = create_note(VAULT_PATH, note_title, note_content)
            st.success(f"Saved: {path}")
            st.info("Rebuild the graph to include the new note.")
            if "draft_content" in st.session_state:
                del st.session_state["draft_content"]

    with n2:
        if note_content:
            st.markdown('<div class="lbl">Preview</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="note-preview">{note_content}</div>', unsafe_allow_html=True)

            existing = [n for n in G.nodes() if G.nodes[n].get("has_note")]
            if existing and note_title:
                st.markdown('<div class="lbl" style="margin-top:1.5rem;">Suggested links</div>',
                            unsafe_allow_html=True)
                with st.spinner("Analyzing..."):
                    suggestions = suggest_links(note_content, existing)
                if suggestions:
                    tags = "".join(f'<span class="link-tag">[[{s}]]</span>' for s in suggestions)
                    st.markdown(f'<div style="margin-top:0.5rem;">{tags}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="font-size:0.82rem;color:#3a3a3a;">No existing notes to link.</div>',
                                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — WEB
# ═══════════════════════════════════════════════════════════════════════════════
with tab_web:
    existing_notes = [n for n in G.nodes() if G.nodes[n].get("has_note")]

    st.markdown("""
    <div style="margin-bottom:2rem;">
      <div style="font-family:'DM Serif Display',serif;font-size:2rem;color:#ede9e1;letter-spacing:-0.5px;">
        Capture the <em style="color:#a89f8c;">web.</em>
      </div>
      <div style="font-size:0.88rem;color:#3a3a3a;margin-top:0.5rem;font-weight:300;">
        Import any article or RSS feed directly into your knowledge graph.
      </div>
    </div>
    """, unsafe_allow_html=True)

    w_tab1, w_tab2, w_tab3 = st.tabs(["Single URL", "Batch URLs", "RSS feeds"])

    # ── Single URL ────────────────────────────────────────────────────────────
    with w_tab1:
        url_input = st.text_input("Article URL", placeholder="https://...",
                                  label_visibility="collapsed")
        fetch_btn = st.button("Import article")

        if fetch_btn and url_input.strip():
            with st.spinner("Fetching and summarizing..."):
                try:
                    result = import_url(url_input.strip(), VAULT_PATH, existing_notes)
                    st.success(f"Saved: {result['title']}")
                    st.markdown(f'<div class="note-preview">{result["summary"]}</div>',
                                unsafe_allow_html=True)
                    if result["links"]:
                        tags = "".join(f'<span class="link-tag">[[{l}]]</span>' for l in result["links"])
                        st.markdown(f'<div style="margin-top:1rem;">{tags}</div>', unsafe_allow_html=True)
                    st.info("Rebuild the graph to include this article.")
                except Exception as e:
                    st.error(str(e))

    # ── Batch URLs ────────────────────────────────────────────────────────────
    with w_tab2:
        batch_input = st.text_area("One URL per line", height=150,
                                   placeholder="https://article1.com\nhttps://article2.com",
                                   label_visibility="collapsed")
        batch_btn = st.button("Import all")

        if batch_btn and batch_input.strip():
            urls = [u.strip() for u in batch_input.strip().split("\n") if u.strip()]
            prog = st.progress(0, text="Starting...")
            results = []

            for i, url in enumerate(urls):
                prog.progress(int((i / len(urls)) * 100), text=f"Importing {i+1}/{len(urls)}...")
                try:
                    r = import_url(url, VAULT_PATH, existing_notes)
                    results.append({"url": url, "status": "ok", "title": r["title"]})
                except Exception as e:
                    results.append({"url": url, "status": "error", "error": str(e)})

            prog.progress(100, text="Done.")
            prog.empty()

            for r in results:
                if r["status"] == "ok":
                    st.markdown(f'<div style="font-size:0.85rem;color:#6ab187;padding:4px 0;">OK &nbsp; {r["title"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="font-size:0.85rem;color:#c0726a;padding:4px 0;">Error &nbsp; {r["url"]} — {r.get("error","")}</div>', unsafe_allow_html=True)

            st.info("Rebuild the graph to include new articles.")

    # ── RSS feeds ─────────────────────────────────────────────────────────────
    with w_tab3:
        feeds = load_feeds()

        f1, f2 = st.columns([3, 1], gap="large")
        with f1:
            new_feed = st.text_input("Add RSS feed URL",
                                     placeholder="https://example.com/feed.xml",
                                     label_visibility="collapsed")
        with f2:
            add_feed_btn = st.button("Add feed")

        if add_feed_btn and new_feed.strip():
            url = new_feed.strip()
            if url not in feeds:
                feeds.append(url)
                save_feeds(feeds)
                st.rerun()

        if feeds:
            st.markdown('<div class="lbl" style="margin-top:1.5rem;">Saved feeds</div>', unsafe_allow_html=True)
            for i, feed in enumerate(feeds):
                fc1, fc2, fc3 = st.columns([4, 1, 1])
                with fc1:
                    st.markdown(f'<div style="font-size:0.85rem;color:#5a5a5a;padding:8px 0;">{feed}</div>', unsafe_allow_html=True)
                with fc2:
                    if st.button("Sync", key=f"sync_{i}"):
                        with st.spinner(f"Syncing..."):
                            results = sync_rss_feed(feed, VAULT_PATH, existing_notes, max_items=5)
                        ok = sum(1 for r in results if r["status"] == "ok")
                        st.success(f"{ok}/{len(results)} articles imported")
                        st.info("Rebuild the graph to include new articles.")
                with fc3:
                    if st.button("Remove", key=f"del_{i}"):
                        feeds.pop(i)
                        save_feeds(feeds)
                        st.rerun()
        else:
            st.markdown('<div style="font-size:0.82rem;color:#2a2a2a;margin-top:1rem;">No feeds saved yet.</div>', unsafe_allow_html=True)
