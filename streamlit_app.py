"""
Streamlit Web Interface for Multi-Agent Report Generator.

Provides an interactive UI for generating, evaluating, and refining research reports.
"""

import streamlit as st
from streamlit_option_menu import option_menu
import json
from datetime import datetime
from pathlib import Path
import time

from report_generator import (
    generate_report,
    ReportState,
    ReviewScore,
    CriticReview,
)


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Multi-Agent Report Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .score-high {
        color: #28a745;
        font-weight: bold;
    }
    .score-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .score-low {
        color: #dc3545;
        font-weight: bold;
    }
    .section-header {
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_score_color(score: float) -> str:
    """Get color class based on score."""
    if score >= 7.0:
        return "score-high"
    elif score >= 5.0:
        return "score-medium"
    else:
        return "score-low"


def format_score_bar(score: float, max_score: float = 10.0) -> None:
    """Display a visual score bar."""
    percentage = (score / max_score) * 100
    if score >= 7.0:
        color = "🟢"
    elif score >= 5.0:
        color = "🟡"
    else:
        color = "🔴"
    st.progress(percentage / 100, text=f"{color} {score:.1f}/{max_score}")


def save_report(report_content: str, metadata: dict) -> str:
    """Save report to file and return filepath."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/report_{timestamp}.md"

    Path("reports").mkdir(exist_ok=True)

    # Prepare full report with metadata
    full_content = f"""# Research Report
**Topic:** {metadata.get('topic', 'N/A')}
**Report Type:** {metadata.get('report_type', 'N/A')}
**Generated:** {metadata.get('timestamp', 'N/A')}
**Quality Score:** {metadata.get('final_score', 'N/A')}/10

---

{report_content}

---

## Generation Metadata
- **Iterations:** {metadata.get('iterations_completed', 0)}
- **Quality Threshold Met:** {metadata.get('quality_threshold_met', False)}
- **Final Review:** {json.dumps(metadata.get('final_review'), indent=2, default=str)}
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    return filename


# ============================================================================
# PAGE: HOME
# ============================================================================

def page_home():
    """Home page with report generation form."""
    st.title("📊 Multi-Agent Report Generator")
    st.markdown("""
    Generate high-quality, well-researched reports on any topic using an advanced
    multi-agent orchestration system powered by LangGraph and Claude AI.
    """)

    with st.container(border=True):
        st.markdown("### 🎯 Generate New Report")

        col1, col2 = st.columns(2)

        with col1:
            topic = st.text_input(
                "Research Topic",
                placeholder="e.g., Latest advances in quantum computing",
                help="Enter the topic you want a report on"
            )

        with col2:
            report_type = st.selectbox(
                "Report Type",
                ["academic", "business", "technical", "news-style"],
                help="Choose the style and structure of the report"
            )

        col3, col4 = st.columns(2)

        with col3:
            quality_threshold = st.slider(
                "Quality Threshold",
                min_value=5.0,
                max_value=10.0,
                value=7.0,
                step=0.5,
                help="Minimum quality score (0-10) to consider report complete"
            )

        with col4:
            max_iterations = st.number_input(
                "Max Iterations",
                min_value=1,
                max_value=10,
                value=6,
                help="Maximum refinement iterations"
            )

        if st.button("🚀 Generate Report", use_container_width=True, type="primary"):
            if not topic.strip():
                st.error("Please enter a research topic!")
            else:
                # Create progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()

                with st.spinner("Generating report... This may take a few minutes."):
                    try:
                        status_text.info("🔍 Initiating research phase...")
                        progress_bar.progress(20)

                        result = generate_report(
                            topic=topic,
                            report_type=report_type,
                            quality_threshold=quality_threshold,
                            max_iterations=max_iterations,
                        )

                        progress_bar.progress(100)
                        status_text.success("✅ Report generation complete!")

                        # Store result in session state
                        st.session_state.last_result = result

                        # Show results in tabs
                        tab1, tab2, tab3 = st.tabs(["📄 Report", "📊 Evaluation", "📈 History"])

                        with tab1:
                            st.markdown("### Generated Report")
                            st.markdown(result["final_report"])

                            # Download button
                            report_file = save_report(
                                result["final_report"],
                                result
                            )

                            with open(report_file, "r") as f:
                                st.download_button(
                                    label="📥 Download Report (MD)",
                                    data=f.read(),
                                    file_name=Path(report_file).name,
                                    mime="text/markdown",
                                )

                        with tab2:
                            st.markdown("### Quality Evaluation")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric(
                                    "Overall Score",
                                    f"{result['final_score']:.1f}",
                                    f"Target: {quality_threshold}",
                                    delta_color="off"
                                )

                            with col2:
                                st.metric(
                                    "Iterations",
                                    result['iterations_completed'],
                                    f"Max: {max_iterations}"
                                )

                            with col3:
                                status = "✅ Pass" if result['quality_threshold_met'] else "⏳ Incomplete"
                                st.metric("Status", status)

                            if result.get("final_review"):
                                review = result["final_review"]
                                score = review.get("score", {})

                                st.markdown("#### Dimension Scores")

                                col1, col2 = st.columns(2)

                                dimensions = [
                                    ("Factual Accuracy", score.get("factual_accuracy", 0)),
                                    ("Completeness", score.get("completeness", 0)),
                                    ("Clarity & Readability", score.get("clarity", 0)),
                                    ("Structure", score.get("structure", 0)),
                                    ("Depth", score.get("depth", 0)),
                                ]

                                with col1:
                                    for dim_name, dim_score in dimensions[:3]:
                                        st.write(f"**{dim_name}**")
                                        format_score_bar(dim_score)

                                with col2:
                                    for dim_name, dim_score in dimensions[3:]:
                                        st.write(f"**{dim_name}**")
                                        format_score_bar(dim_score)

                                # Strengths and Weaknesses
                                st.markdown("#### Key Strengths")
                                for i, strength in enumerate(review.get("strengths", []), 1):
                                    st.success(f"{i}. {strength}")

                                st.markdown("#### Areas for Improvement")
                                for i, weakness in enumerate(review.get("weaknesses", []), 1):
                                    st.warning(f"{i}. {weakness}")

                                st.markdown("#### Suggestions for Next Report")
                                for i, suggestion in enumerate(review.get("suggestions", []), 1):
                                    st.info(f"{i}. {suggestion}")

                        with tab3:
                            st.markdown("### Refinement History")

                            if result["refinement_history"]:
                                for iteration_data in result["refinement_history"]:
                                    with st.expander(f"Iteration {iteration_data['iteration']}"):
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write(f"**Previous Score:** {iteration_data['previous_score']:.1f}/10")
                                        with col2:
                                            st.write(f"**Timestamp:** {iteration_data['timestamp']}")

                                        st.write("**Changes Made:**")
                                        for change in iteration_data['changes_made']:
                                            st.write(f"- {change}")
                            else:
                                st.info("No refinement iterations performed.")

                        st.balloons()

                    except Exception as e:
                        status_text.error(f"❌ Error: {str(e)}")
                        st.error(f"An error occurred: {str(e)}")


# ============================================================================
# PAGE: HISTORY
# ============================================================================

def page_history():
    """Display previously generated reports."""
    st.title("📚 Report History")

    reports_dir = Path("reports")

    if not reports_dir.exists():
        st.info("No reports generated yet. Go to Home to create one!")
        return

    report_files = list(reports_dir.glob("*.md"))

    if not report_files:
        st.info("No reports found in history.")
        return

    # Sort by modification time (newest first)
    report_files = sorted(report_files, key=lambda x: x.stat().st_mtime, reverse=True)

    st.markdown(f"### Found {len(report_files)} reports")

    for report_file in report_files:
        with st.expander(f"📄 {report_file.name}"):
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract metadata from file
            lines = content.split("\n")
            metadata = {}
            for line in lines[:10]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Topic:** {metadata.get('Topic', 'N/A')}")
            with col2:
                st.write(f"**Type:** {metadata.get('Report Type', 'N/A')}")
            with col3:
                st.write(f"**Generated:** {metadata.get('Generated', 'N/A')}")

            # Preview
            st.markdown("#### Preview")
            preview_lines = content.split("\n")[15:25]
            st.text("\n".join(preview_lines))

            # Download button
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Download",
                    data=content,
                    file_name=report_file.name,
                    mime="text/markdown",
                    key=f"download_{report_file.name}"
                )

            with col2:
                if st.button("🗑️ Delete", key=f"delete_{report_file.name}"):
                    report_file.unlink()
                    st.success("Report deleted!")
                    st.rerun()


# ============================================================================
# PAGE: SETTINGS
# ============================================================================

def page_settings():
    """Settings and configuration page."""
    st.title("⚙️ Settings & Configuration")

    st.markdown("### API Configuration")
    st.info("""
    This application requires the following API keys configured in your `.env` file:
    - `ANTHROPIC_API_KEY` - Claude AI API key
    - `TAVILY_API_KEY` - Tavily search API key
    """)

    st.markdown("### About")
    st.markdown("""
    **Multi-Agent Report Generator v1.0**

    A sophisticated research orchestration system that combines:
    - 🔍 Web research and deep content scraping
    - ✍️ Intelligent report synthesis
    - 🧐 Critical quality evaluation
    - 🔄 Iterative refinement

    Built with LangGraph, Claude AI, and Streamlit.
    """)

    st.markdown("### System Information")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Python Version:** 3.10+")
        st.write("**Framework:** Streamlit")
        st.write("**LLM:** Claude 3.5 Sonnet")

    with col2:
        st.write("**Search Engine:** Tavily API")
        st.write("**Orchestration:** LangGraph")
        st.write("**Version:** 1.0.0")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""

    # Initialize session state
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    # Sidebar navigation
    with st.sidebar:
        st.logo("https://raw.githubusercontent.com/streamlit/streamlit/develop/docs/static/img/streamlit_logo.svg")
        st.title("Navigation")

        page = option_menu(
            "Select Page",
            ["Home", "History", "Settings"],
            icons=["house", "book", "gear"],
            menu_icon="cast",
            default_index=0,
        )

    # Route to pages
    if page == "Home":
        page_home()
    elif page == "History":
        page_history()
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
