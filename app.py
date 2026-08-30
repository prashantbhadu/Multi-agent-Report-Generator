"""
Streamlit UI for the multi-agent research pipeline (pipeline.py).

Run with:
    streamlit run app.py

This file expects `pipeline.py` (and its `agents.py` dependency) to be
in the same folder / on the PYTHONPATH, since it imports
`run_research_pipeline` from it.
"""

import time
import threading
from datetime import datetime

import streamlit as st
from pipeline import run_research_pipeline


# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="Scout // Multi-Agent Research",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# DESIGN TOKENS  (edit these to re-theme the whole app)
# ============================================================================
BG_MAIN     = "#0a0e16"
BG_PANEL    = "#111826"
BG_PANEL_2  = "#0d1320"
BORDER      = "#212b3d"
BORDER_SOFT = "#1a2333"
TEXT_HI     = "#e7ecf5"
TEXT_MUT    = "#7c8798"
TEXT_DIM    = "#4b5568"
CYAN        = "#35e3e0"
PURPLE      = "#9b8cf5"
GREEN       = "#3ddc97"
AMBER       = "#f5b942"
RED         = "#f5687b"

AGENTS = [
    {"key": "scout",  "label": "Scout",  "sub": "Web Search",   "icon": "◎"},
    {"key": "reader", "label": "Reader", "sub": "Deep Scrape",  "icon": "▤"},
    {"key": "writer", "label": "Writer", "sub": "Synthesis",    "icon": "✎"},
    {"key": "critic", "label": "Critic", "sub": "Review",       "icon": "◆"},
]

# ============================================================================
# GLOBAL CSS
# ============================================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}

.stApp {{
    background:
        radial-gradient(ellipse 900px 500px at 15% -10%, rgba(53,227,224,0.07), transparent 60%),
        radial-gradient(ellipse 900px 500px at 85% 0%, rgba(155,140,245,0.06), transparent 60%),
        {BG_MAIN};
}}

#MainMenu, footer, header {{visibility: hidden;}}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1180px; }}

/* ---------- Topbar ---------- */
.topbar {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; margin-bottom: 22px;
    background: linear-gradient(180deg, {BG_PANEL}, {BG_PANEL_2});
    border: 1px solid {BORDER}; border-radius: 12px;
}}
.topbar-left {{ display: flex; align-items: center; gap: 12px; }}
.topbar-badge {{
    width: 38px; height: 38px; border-radius: 9px;
    background: linear-gradient(135deg, {CYAN}, {PURPLE});
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: #06141a; font-weight: 700;
}}
.topbar-title {{
    font-family: 'JetBrains Mono', monospace; font-weight: 700;
    font-size: 15px; color: {TEXT_HI}; letter-spacing: 0.5px; line-height: 1.1;
}}
.topbar-sub {{ font-size: 11px; color: {TEXT_DIM}; font-family: 'JetBrains Mono', monospace; }}
.topbar-right {{ display: flex; align-items: center; gap: 18px; }}
.topbar-clock {{
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {TEXT_MUT};
    border: 1px solid {BORDER}; padding: 6px 12px; border-radius: 7px; background: {BG_MAIN};
}}
.status-pill {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {GREEN};
    background: rgba(61,220,151,0.1); border: 1px solid rgba(61,220,151,0.35);
    padding: 6px 12px; border-radius: 20px; display:flex; align-items:center; gap:6px;
}}
.status-dot {{ width:6px; height:6px; border-radius:50%; background:{GREEN}; box-shadow: 0 0 8px {GREEN}; }}

/* ---------- Command panel ---------- */
.cmd-label {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {TEXT_DIM};
    letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase;
}}
div[data-testid="stForm"] {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 18px 20px 14px 20px;
}}
div[data-testid="stTextInput"] input {{
    background: {BG_MAIN} !important; color: {TEXT_HI} !important;
    border: 1px solid {BORDER_SOFT} !important; border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 14px !important;
    padding: 12px 14px !important;
}}
div[data-testid="stTextInput"] input:focus {{
    border-color: {CYAN} !important; box-shadow: 0 0 0 1px {CYAN}44 !important;
}}
div[data-testid="stTextInput"] label {{ display: none; }}

.stButton > button, .stFormSubmitButton > button {{
    background: linear-gradient(135deg, {CYAN}, #1fb8c9) !important;
    color: #062024 !important; border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; font-family: 'JetBrains Mono', monospace !important;
    padding: 0.65rem 1rem !important; letter-spacing: 0.3px !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(53,227,224,0.25) !important;
}}

/* ---------- Agent pipeline ---------- */
.pipeline-wrap {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 26px 30px 20px 30px; margin: 20px 0 22px 0;
}}
.pipeline-title {{
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {TEXT_MUT};
    letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 22px;
}}
.pipeline-row {{ display: flex; align-items: flex-start; }}
.pipeline-node {{ display: flex; flex-direction: column; align-items: center; width: 100%; position: relative; }}
.pipeline-connector {{
    flex: 1; height: 2px; margin-top: 25px; background: {BORDER_SOFT}; position: relative; top: 0;
}}
.pipeline-connector.done {{ background: linear-gradient(90deg, {GREEN}, {GREEN}); }}
.node-circle {{
    width: 50px; height: 50px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; border: 2px solid {BORDER_SOFT}; background: {BG_MAIN};
    color: {TEXT_DIM}; transition: all 0.25s ease;
}}
.node-circle.active {{
    border-color: {CYAN}; color: {CYAN}; background: rgba(53,227,224,0.08);
    box-shadow: 0 0 0 6px rgba(53,227,224,0.08), 0 0 18px rgba(53,227,224,0.35);
    animation: pulse 1.4s ease-in-out infinite;
}}
.node-circle.done {{
    border-color: {GREEN}; color: {GREEN}; background: rgba(61,220,151,0.08);
}}
@keyframes pulse {{
    0%, 100% {{ box-shadow: 0 0 0 6px rgba(53,227,224,0.08), 0 0 18px rgba(53,227,224,0.35); }}
    50% {{ box-shadow: 0 0 0 9px rgba(53,227,224,0.12), 0 0 26px rgba(53,227,224,0.5); }}
}}
.node-label {{
    font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 12.5px;
    color: {TEXT_MUT}; margin-top: 10px; letter-spacing: 0.3px;
}}
.node-label.active {{ color: {CYAN}; }}
.node-label.done {{ color: {GREEN}; }}
.node-sub {{ font-size: 10.5px; color: {TEXT_DIM}; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }}
.node-sub.active {{ color: {TEXT_MUT}; }}

/* ---------- Result panel / tabs ---------- */
.stTabs [data-baseweb="tab-list"] {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 10px 10px 0 0;
    padding: 4px 6px 0 6px; gap: 2px;
}}
.stTabs [data-baseweb="tab"] {{
    font-family: 'JetBrains Mono', monospace; font-size: 13px; color: {TEXT_MUT};
    padding: 10px 16px; border-radius: 8px 8px 0 0;
}}
.stTabs [aria-selected="true"] {{
    background: {BG_MAIN} !important; color: {CYAN} !important;
    border-bottom: 2px solid {CYAN} !important;
}}
.tab-body {{
    background: {BG_PANEL_2}; border: 1px solid {BORDER}; border-top: none;
    border-radius: 0 0 10px 10px; padding: 26px 28px;
}}
.tab-body h1, .tab-body h2, .tab-body h3 {{ color: {TEXT_HI}; }}
.tab-body p, .tab-body li {{ color: #cfd6e3; line-height: 1.6; }}
.tab-body a {{ color: {CYAN}; }}

textarea {{
    background: {BG_MAIN} !important; color: {TEXT_MUT} !important;
    border: 1px solid {BORDER_SOFT} !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 12.5px !important;
}}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{
    background: {BG_PANEL_2}; border-right: 1px solid {BORDER};
}}
.side-block {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 14px;
}}
.side-title {{
    font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: {TEXT_DIM};
    text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 10px;
}}
.side-row {{ display:flex; justify-content: space-between; font-size: 12.5px; color: {TEXT_MUT}; padding: 4px 0; }}
.side-row b {{ color: {TEXT_HI}; font-weight: 600; }}
.chip {{
    display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
    padding: 3px 9px; border-radius: 20px; margin: 2px 4px 2px 0;
    border: 1px solid {BORDER_SOFT}; color: {TEXT_MUT};
}}

/* misc */
hr {{ border-color: {BORDER} !important; }}
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-thumb {{ background: {BORDER_SOFT}; border-radius: 6px; }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE
# ============================================================================
if "state" not in st.session_state:
    st.session_state.state = None
if "history" not in st.session_state:
    st.session_state.history = []


# ============================================================================
# TOPBAR
# ============================================================================
now = datetime.now().strftime("%H:%M:%S")
st.markdown(f"""
<div class="topbar">
    <div class="topbar-left">
        <div class="topbar-badge">◈</div>
        <div>
            <div class="topbar-title">MULTI-AGENT RESEARCH ASSISTANT</div>
            <div class="topbar-sub">Search → Reader → Writer → Critic</div>
        </div>
    </div>
    <div class="topbar-right">
        <div class="topbar-clock">{now}</div>
        <div class="status-pill"><span class="status-dot"></span>AGENTS ONLINE</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown('<div class="side-block">', unsafe_allow_html=True)
    st.markdown('<div class="side-title">Pipeline</div>', unsafe_allow_html=True)
    for a in AGENTS:
        st.markdown(
            f'<div class="side-row">{a["icon"]}&nbsp; {a["label"]} '
            f'<b style="margin-left:auto;">{a["sub"]}</b></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-block">', unsafe_allow_html=True)
    st.markdown('<div class="side-title">Stack</div>', unsafe_allow_html=True)
    st.markdown(
        '<span class="chip">LangChain</span><span class="chip">Mistral AI</span>'
        '<span class="chip">Tavily</span><span class="chip">BeautifulSoup4</span>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.history:
        st.markdown('<div class="side-block">', unsafe_allow_html=True)
        st.markdown('<div class="side-title">Recent topics</div>', unsafe_allow_html=True)
        for t in reversed(st.session_state.history[-6:]):
            st.markdown(f'<div class="side-row">• {t}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("＋ New session", use_container_width=True):
        st.session_state.state = None
        st.rerun()


# ============================================================================
# COMMAND INPUT
# ============================================================================
st.markdown('<div class="cmd-label">▸ Research directive</div>', unsafe_allow_html=True)
with st.form("topic_form"):
    c1, c2 = st.columns([5, 1])
    with c1:
        topic = st.text_input(
            "topic",
            placeholder="e.g. Latest advances in solid-state batteries",
            label_visibility="collapsed",
        )
    with c2:
        submitted = st.form_submit_button("▶ Run", use_container_width=True)


# ============================================================================
# PIPELINE VISUAL — renders the 4 agent nodes at a given "active index"
# active_index == -1        -> all idle
# active_index in [0..3]    -> that node pulsing, previous nodes marked done
# active_index == 4         -> all done
# ============================================================================
def render_pipeline(active_index: int, placeholder=None):
    nodes_html = []
    for i, a in enumerate(AGENTS):
        if active_index > i or active_index == 4:
            state = "done"
            circle = "✓"
        elif active_index == i:
            state = "active"
            circle = a["icon"]
        else:
            state = ""
            circle = a["icon"]

        nodes_html.append(f"""
        <div class="pipeline-node">
            <div class="node-circle {state}">{circle}</div>
            <div class="node-label {state}">{a['label']}</div>
            <div class="node-sub {state}">{a['sub']}</div>
        </div>
        """)
        if i < len(AGENTS) - 1:
            conn_state = "done" if (active_index > i or active_index == 4) else ""
            nodes_html.append(f'<div class="pipeline-connector {conn_state}"></div>')

    html = f"""
    <div class="pipeline-wrap">
        <div class="pipeline-title">Live agent status</div>
        <div class="pipeline-row">{''.join(nodes_html)}</div>
    </div>
    """
    if placeholder is not None:
        placeholder.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)


def run_with_progress(topic: str) -> dict:
    """Runs run_research_pipeline() in a background thread while animating
    the agent pipeline in the foreground, so the UI stays live instead of
    freezing behind a single spinner."""
    result = {}

    def worker():
        result["state"] = run_research_pipeline(topic)

    placeholder = st.empty()
    thread = threading.Thread(target=worker)
    thread.start()

    step = 0
    while thread.is_alive():
        render_pipeline(step % len(AGENTS), placeholder)
        time.sleep(1.1)
        step += 1

    thread.join()
    render_pipeline(4, placeholder)
    return result.get("state", {})


# ============================================================================
# RUN
# ============================================================================
if submitted:
    if not topic.strip():
        st.warning("Enter a research topic before running the pipeline.")
    else:
        st.session_state.history.append(topic.strip())
        st.session_state.state = run_with_progress(topic.strip())
elif st.session_state.state is None:
    render_pipeline(-1)


# ============================================================================
# RESULTS
# ============================================================================
state = st.session_state.state

if state:
    report = state.get("report", "_No report generated._")
    feedback = state.get("feedback", "_No feedback generated._")
    research = state.get("research", "")
    scraped = state.get("scraped_content", "")

    tab_report, tab_feedback, tab_research, tab_scraped = st.tabs(
        ["📄  Report", "🧐  Critic Review", "🔍  Search Results", "📚  Scraped Content"]
    )

    with tab_report:
        st.markdown(f'<div class="tab-body">{report}</div>', unsafe_allow_html=True)
        st.download_button(
            "⭳ Download report (.md)",
            data=str(report),
            file_name="research_report.md",
            mime="text/markdown",
        )

    with tab_feedback:
        st.markdown(f'<div class="tab-body">{feedback}</div>', unsafe_allow_html=True)

    with tab_research:
        st.markdown('<div class="tab-body">', unsafe_allow_html=True)
        st.text_area("Raw search agent output", value=research, height=320, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_scraped:
        st.markdown('<div class="tab-body">', unsafe_allow_html=True)
        st.text_area("Raw reader agent output", value=scraped, height=320, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown(
        f'<div style="text-align:center; padding: 30px 0 10px 0; '
        f'color:{TEXT_DIM}; font-family:\'JetBrains Mono\', monospace; font-size:13px;">'
        f'Enter a topic above and press <b style="color:{CYAN};">▶ Run</b> to launch the pipeline.'
        f'</div>',
        unsafe_allow_html=True,
    )