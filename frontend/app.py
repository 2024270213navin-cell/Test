"""
frontend/app.py — Streamlit UI for ServiceNow AI Automation.

Pages:
  📁 Knowledge Base  — Upload / ingest / delete Excel files
  🔍 AI Assistant    — Chat interface with the RAG system
  📊 System Status   — Health dashboard
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_V3 = f"{API_BASE}/api/v3"
REQUEST_TIMEOUT = 180  # seconds — long to allow LLM inference

st.set_page_config(
    page_title="ServiceNow AI Automation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  Custom CSS
# ─────────────────────────────────────────────

st.markdown(
    """
<style>
    /* Main brand colours */
    :root {
        --primary: #0052CC;
        --secondary: #00B8D9;
        --success: #36B37E;
        --warning: #FFAB00;
        --danger:  #FF5630;
        --surface: #F4F5F7;
    }

    /* Header bar */
    .header-bar {
        background: linear-gradient(135deg, #0052CC 0%, #0065FF 100%);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 16px rgba(0,82,204,0.25);
    }
    .header-bar h1 { color: #fff; margin: 0; font-size: 1.8rem; }
    .header-bar p  { color: rgba(255,255,255,0.82); margin: 0.25rem 0 0; font-size: 0.95rem; }

    /* Metric cards */
    .metric-card {
        background: #fff;
        border: 1px solid #DFE1E6;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: var(--primary); }
    .metric-card .label { font-size: 0.8rem; color: #6B778C; text-transform: uppercase; letter-spacing: 0.05em; }

    /* Chat bubbles */
    .chat-user {
        background: #DEEBFF;
        border-radius: 12px 12px 4px 12px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
        color: #172B4D;
    }
    .chat-assistant {
        background: #F4F5F7;
        border-left: 4px solid var(--primary);
        border-radius: 4px 12px 12px 12px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 90%;
        color: #172B4D;
    }
    .context-badge {
        display: inline-block;
        background: #E3FCEF;
        color: #006644;
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.78rem;
        margin: 2px;
    }

    /* Status indicators */
    .status-ok   { color: #36B37E; font-weight: 600; }
    .status-fail { color: #FF5630; font-weight: 600; }
    .status-warn { color: #FFAB00; font-weight: 600; }

    /* File table */
    .file-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.6rem 1rem;
        border-bottom: 1px solid #DFE1E6;
        font-size: 0.9rem;
    }
    .ingested-badge {
        background: #E3FCEF; color: #006644;
        border-radius: 4px; padding: 2px 8px; font-size: 0.75rem;
    }
    .pending-badge {
        background: #FFFAE6; color: #7A5900;
        border-radius: 4px; padding: 2px 8px; font-size: 0.75rem;
    }

    /* Scrollable chat window */
    .chat-window {
        height: 460px;
        overflow-y: auto;
        padding: 0.5rem;
        border: 1px solid #DFE1E6;
        border-radius: 10px;
        background: #fff;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
#  API helpers
# ─────────────────────────────────────────────

def api_get(path: str) -> tuple[bool, dict | list]:
    try:
        resp = requests.get(f"{API_BASE}{path}", timeout=10)
        return resp.ok, resp.json()
    except requests.ConnectionError:
        return False, {"error": f"Cannot connect to API at {API_BASE}"}
    except Exception as exc:
        return False, {"error": str(exc)}


def api_post(path: str, payload: dict, timeout: int = REQUEST_TIMEOUT) -> tuple[bool, dict]:
    try:
        resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
        return resp.ok, resp.json()
    except requests.ConnectionError:
        return False, {"error": f"Cannot connect to API at {API_BASE}"}
    except Exception as exc:
        return False, {"error": str(exc)}


def api_post_file(path: str, file_bytes: bytes, filename: str) -> tuple[bool, dict]:
    try:
        resp = requests.post(
            f"{API_BASE}{path}",
            files={"file": (filename, file_bytes, "application/octet-stream")},
            timeout=60,
        )
        return resp.ok, resp.json()
    except requests.ConnectionError:
        return False, {"error": f"Cannot connect to API at {API_BASE}"}
    except Exception as exc:
        return False, {"error": str(exc)}


def api_delete(path: str) -> tuple[bool, dict]:
    try:
        resp = requests.delete(f"{API_BASE}{path}", timeout=10)
        return resp.ok, resp.json()
    except Exception as exc:
        return False, {"error": str(exc)}


# ─────────────────────────────────────────────
#  Session state init
# ─────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # list of {"role": ..., "content": ..., "context": [...]}
if "api_history" not in st.session_state:
    st.session_state.api_history = []    # slim history sent to API


# ─────────────────────────────────────────────
#  Sidebar navigation
# ─────────────────────────────────────────────

st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 1rem 0 0.5rem;">
        <span style="font-size:2.5rem;">🤖</span>
        <h3 style="margin:0.3rem 0 0; color:#0052CC;">ServiceNow AI</h3>
        <small style="color:#6B778C;">Powered by Ollama · Gemma</small>
    </div>
    <hr style="margin:1rem 0; border-color:#DFE1E6;">
    """,
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigate",
    ["🔍 AI Assistant", "📁 Knowledge Base", "📊 System Status"],
    label_visibility="collapsed",
)

st.sidebar.markdown("<hr style='border-color:#DFE1E6;'>", unsafe_allow_html=True)
st.sidebar.markdown(
    f"""
    <small style='color:#6B778C;'>
    <b>API:</b> {API_BASE}<br>
    <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
    </small>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
#  Page: AI Assistant
# ─────────────────────────────────────────────

def page_assistant():
    st.markdown(
        """
        <div class="header-bar">
          <h1>🔍 AI Ticket Assistant</h1>
          <p>Ask any IT support question — powered by Gemma via Ollama RAG pipeline</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_chat, col_meta = st.columns([3, 1])

    with col_chat:
        # Chat history display
        chat_container = st.container(height=460, border=True)
        with chat_container:
            for turn in st.session_state.chat_history:
                if turn["role"] == "user":
                    st.markdown(
                        f'<div class="chat-user">👤 {turn["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="chat-assistant">🤖 {turn["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                    # Show context sources
                    if turn.get("context"):
                        badges = "".join(
                            f'<span class="context-badge">📎 {c["category"]} · {c["similarity_score"]:.0%}</span>'
                            for c in turn["context"]
                        )
                        st.markdown(
                            f'<div style="margin-top:0.3rem;">{badges}</div>',
                            unsafe_allow_html=True,
                        )

        # Input row
        with st.form("chat_form", clear_on_submit=True):
            inp_col, btn_col = st.columns([5, 1])
            with inp_col:
                user_input = st.text_input(
                    "Your question",
                    placeholder="e.g. How do I reset my VPN password?",
                    label_visibility="collapsed",
                )
            with btn_col:
                submitted = st.form_submit_button("Send ➤", use_container_width=True)

        if submitted and user_input.strip():
            _send_message(user_input.strip())
            st.rerun()

        # Clear chat button
        if st.session_state.chat_history:
            if st.button("🗑 Clear conversation"):
                st.session_state.chat_history = []
                st.session_state.api_history = []
                st.rerun()

    with col_meta:
        st.markdown("#### 📌 Session Stats")
        turns = len([t for t in st.session_state.chat_history if t["role"] == "user"])
        st.metric("Questions asked", turns)

        if st.session_state.chat_history:
            last_assistant = next(
                (t for t in reversed(st.session_state.chat_history) if t["role"] == "assistant"),
                None,
            )
            if last_assistant:
                st.markdown("#### 🔗 Last Context Sources")
                for c in last_assistant.get("context", []):
                    st.markdown(
                        f"""
                        <div style="background:#F4F5F7;border-radius:8px;padding:0.5rem;margin:0.3rem 0;font-size:0.82rem;">
                          <b>{c.get('category','N/A')}</b><br>
                          <span style="color:#6B778C;">{c.get('question','')[:60]}…</span><br>
                          <span style="color:#36B37E;">{c.get('similarity_score',0):.0%} match</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


def _send_message(question: str):
    st.session_state.chat_history.append({"role": "user", "content": question})

    with st.spinner("🤔 Thinking…"):
        ok, data = api_post(
            "/api/v3/search",
            {
                "question": question,
                "key": "en",
                "history": st.session_state.api_history[-6:],  # last 3 turns
            },
        )

    if ok:
        answer = data.get("response", "No response received.")
        context = data.get("context", [])
        st.session_state.chat_history.append(
            {"role": "assistant", "content": answer, "context": context}
        )
        # Update slim API history
        st.session_state.api_history.append({"role": "user", "content": question})
        st.session_state.api_history.append({"role": "assistant", "content": answer})
    else:
        error_msg = data.get("detail") or data.get("error") or "Unknown error"
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": f"⚠️ Error: {error_msg}",
                "context": [],
            }
        )


# ─────────────────────────────────────────────
#  Page: Knowledge Base
# ─────────────────────────────────────────────

def page_knowledge_base():
    st.markdown(
        """
        <div class="header-bar">
          <h1>📁 Knowledge Base Manager</h1>
          <p>Upload, ingest, and manage Excel knowledge-base files</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_upload, tab_files = st.tabs(["⬆️ Upload New File", "📋 Manage Files"])

    # ── Upload tab
    with tab_upload:
        st.markdown("#### Upload Excel Knowledge Base")
        st.info(
            "Required columns: **Category**, **Question**, **Response**, **Reference Information**",
            icon="ℹ️",
        )

        uploaded = st.file_uploader(
            "Select Excel file (.xlsx)",
            type=["xlsx", "xls"],
            label_visibility="collapsed",
        )

        if uploaded:
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown(f"**File:** `{uploaded.name}`")
                st.markdown(f"**Size:** {uploaded.size / 1024:.1f} KB")

            # Preview
            try:
                df_preview = pd.read_excel(uploaded, nrows=10)
                st.markdown("**Preview (first 10 rows):**")
                st.dataframe(df_preview, use_container_width=True)
            except Exception as exc:
                st.warning(f"Could not preview: {exc}")

            col_up, col_ingest = st.columns(2)

            with col_up:
                if st.button("⬆️ Upload File", use_container_width=True, type="primary"):
                    uploaded.seek(0)
                    with st.spinner("Uploading…"):
                        ok, data = api_post_file("/api/v3/files/upload", uploaded.read(), uploaded.name)
                    if ok:
                        st.success(f"✅ Uploaded `{data['filename']}` ({data['row_count']} rows)")
                    else:
                        st.error(f"Upload failed: {data.get('detail') or data.get('error')}")

            with col_ingest:
                if st.button("⚡ Upload & Ingest", use_container_width=True, type="secondary"):
                    uploaded.seek(0)
                    file_bytes = uploaded.read()
                    with st.spinner("Uploading…"):
                        ok_up, data_up = api_post_file("/api/v3/files/upload", file_bytes, uploaded.name)

                    if ok_up:
                        st.success(f"✅ Uploaded `{data_up['filename']}`")
                        fname = data_up["filename"]
                        with st.spinner(f"Ingesting `{fname}` into FAISS…"):
                            ok_ing, data_ing = api_post(f"/api/v3/files/{fname}/ingest", {})
                        if ok_ing:
                            st.success(
                                f"⚡ Ingested {data_ing['chunks_indexed']} chunks from `{fname}`"
                            )
                        else:
                            st.error(f"Ingest failed: {data_ing.get('detail') or data_ing.get('error')}")
                    else:
                        st.error(f"Upload failed: {data_up.get('detail') or data_up.get('error')}")

    # ── Manage files tab
    with tab_files:
        st.markdown("#### Uploaded Files")
        ok, files_data = api_get("/api/v3/files")

        if not ok:
            st.error(f"Cannot fetch file list: {files_data.get('error')}")
            return

        if not files_data:
            st.info("No files uploaded yet. Use the Upload tab to add a knowledge base.")
            return

        for f in files_data:
            fname = f["filename"]
            with st.container():
                col_name, col_rows, col_status, col_actions = st.columns([3, 1, 1, 2])

                with col_name:
                    st.markdown(f"📄 **{fname}**")
                    size_kb = f["size_bytes"] / 1024
                    st.caption(f"{size_kb:.1f} KB · uploaded {f['uploaded_at'][:10]}")

                with col_rows:
                    st.metric("Rows", f["row_count"])

                with col_status:
                    if f.get("ingested"):
                        st.markdown('<span class="ingested-badge">✅ Ingested</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="pending-badge">⏳ Pending</span>', unsafe_allow_html=True)

                with col_actions:
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        if st.button("⚡", key=f"ingest_{fname}", help="Ingest into FAISS"):
                            with st.spinner(f"Ingesting {fname}…"):
                                ok_i, d_i = api_post(f"/api/v3/files/{fname}/ingest", {})
                            if ok_i:
                                st.success(f"Ingested {d_i['chunks_indexed']} chunks")
                                st.rerun()
                            else:
                                st.error(d_i.get("detail") or d_i.get("error"))

                    with btn_col2:
                        if st.button("👁", key=f"preview_{fname}", help="Preview contents"):
                            ok_p, pdata = api_get(f"/api/v3/files/{fname}/preview")
                            if ok_p:
                                st.dataframe(
                                    pd.DataFrame(pdata["rows"]),
                                    use_container_width=True,
                                )

                    with btn_col3:
                        if st.button("🗑", key=f"del_{fname}", help="Delete file"):
                            ok_d, d_d = api_delete(f"/api/v3/files/{fname}")
                            if ok_d:
                                st.success(f"Deleted `{fname}`")
                                st.rerun()
                            else:
                                st.error(d_d.get("detail") or d_d.get("error"))

                st.divider()


# ─────────────────────────────────────────────
#  Page: System Status
# ─────────────────────────────────────────────

def page_status():
    st.markdown(
        """
        <div class="header-bar">
          <h1>📊 System Status</h1>
          <p>Real-time health of all components</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ok, health = api_get("/health")

    if not ok:
        st.error(f"⚠️ Cannot reach API at `{API_BASE}`. Is the backend running?")
        st.code(f"cd servicenow-ai && python -m backend.main", language="bash")
        return

    # Metric cards
    col1, col2, col3, col4 = st.columns(4)

    status_emoji = "✅" if health.get("status") == "healthy" else "⚠️"
    with col1:
        st.markdown(
            f"""<div class="metric-card">
            <div class="value">{status_emoji}</div>
            <div class="label">Overall Status</div>
            </div>""",
            unsafe_allow_html=True,
        )

    ollama_ok = health.get("ollama_reachable", False)
    with col2:
        st.markdown(
            f"""<div class="metric-card">
            <div class="value">{'🟢' if ollama_ok else '🔴'}</div>
            <div class="label">Ollama LLM</div>
            </div>""",
            unsafe_allow_html=True,
        )

    faiss_ok = health.get("faiss_loaded", False)
    with col3:
        st.markdown(
            f"""<div class="metric-card">
            <div class="value">{'🟢' if faiss_ok else '🔴'}</div>
            <div class="label">FAISS Index</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""<div class="metric-card">
            <div class="value">{health.get('indexed_chunks', 0):,}</div>
            <div class="label">Indexed Chunks</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Detailed status table
    st.markdown("#### Component Details")
    details = {
        "Component": ["FastAPI Backend", "Ollama (Gemma)", "FAISS Vector DB", "Embedding Model"],
        "Status": [
            "🟢 Online",
            "🟢 Reachable" if ollama_ok else "🔴 Unreachable",
            "🟢 Loaded" if faiss_ok else "🔴 Not Loaded",
            "🟢 Ready" if faiss_ok else "⚪ Idle",
        ],
        "Detail": [
            f"v{health.get('version', '3.0.0')}",
            "gemma4:31b-cloud via /api/generate",
            f"{health.get('indexed_chunks', 0):,} vectors",
            "all-MiniLM-L6-v2",
        ],
    }
    st.table(pd.DataFrame(details))

    st.markdown("---")
    st.markdown("#### Quick Actions")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Refresh Status"):
            st.rerun()
    with c2:
        st.markdown(f"**API Docs:** [{API_BASE}/docs]({API_BASE}/docs)")


# ─────────────────────────────────────────────
#  Router
# ─────────────────────────────────────────────

if page == "🔍 AI Assistant":
    page_assistant()
elif page == "📁 Knowledge Base":
    page_knowledge_base()
elif page == "📊 System Status":
    page_status()
