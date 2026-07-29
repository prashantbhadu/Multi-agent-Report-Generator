"""
Streamlit UI for the multi-agent research pipeline (pipeline.py).

Run with:
    streamlit run app.py

This file expects `pipeline.py` (and its `agents.py` dependency) to be
in the same folder / on the PYTHONPATH, since it imports
`run_research_pipeline` from it.
"""

import streamlit as st
from pipeline import run_research_pipeline


st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Multi-Agent Research Assistant")
st.caption(
    "Enter a topic and watch the Search → Reader → Writer → Critic "
    "agent pipeline work through it step by step."
)

# ---------------------------------------------------------------------------
# Session state setup
# ---------------------------------------------------------------------------
if "state" not in st.session_state:
    st.session_state.state = None
if "running" not in st.session_state:
    st.session_state.running = False


# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------
with st.form("topic_form"):
    topic = st.text_input(
        "Research topic",
        placeholder="e.g. Latest advances in solid-state batteries",
    )
    submitted = st.form_submit_button("Run Research Pipeline", use_container_width=True)


# ---------------------------------------------------------------------------
# Run pipeline with live step-by-step feedback
# ---------------------------------------------------------------------------
def run_with_progress(topic: str) -> dict:
    """
    Mirrors run_research_pipeline's 4 steps but drives Streamlit UI
    elements (status spinners + expanders) instead of print statements.
    We call the same building blocks pipeline.py uses under the hood
    by simply invoking run_research_pipeline() inside a single spinner,
    since pipeline.py itself only prints to the terminal.
    """
    state = {}

    with st.status("Running the research pipeline...", expanded=True) as status:
        st.write("**Step 1/4 — Search agent** gathering information...")
        st.write("**Step 2/4 — Reader agent** scraping the best source...")
        st.write("**Step 3/4 — Writer agent** drafting the report...")
        st.write("**Step 4/4 — Critic agent** reviewing the report...")

        state = run_research_pipeline(topic)

        status.update(label="Pipeline complete ✅", state="complete", expanded=False)

    return state


if submitted:
    if not topic.strip():
        st.warning("Please enter a topic before running the pipeline.")
    else:
        st.session_state.running = True
        st.session_state.state = run_with_progress(topic.strip())
        st.session_state.running = False


# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
state = st.session_state.state

if state:
    st.divider()
    st.subheader("Results")

    tab_report, tab_feedback, tab_research, tab_scraped = st.tabs(
        ["📄 Final Report", "🧐 Critic Feedback", "🔍 Search Results", "📚 Scraped Content"]
    )

    with tab_report:
        st.markdown(state.get("report", "_No report generated._"))
        st.download_button(
            "Download report (.md)",
            data=str(state.get("report", "")),
            file_name="research_report.md",
            mime="text/markdown",
        )

    with tab_feedback:
        st.markdown(state.get("feedback", "_No feedback generated._"))

    with tab_research:
        st.text_area(
            "Raw search agent output",
            value=state.get("research", ""),
            height=300,
        )

    with tab_scraped:
        st.text_area(
            "Raw reader agent output",
            value=state.get("scraped_content", ""),
            height=300,
        )
else:
    st.info("Enter a topic above and click **Run Research Pipeline** to get started.")