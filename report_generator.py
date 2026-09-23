"""
Advanced Multi-Agent Report Generation System using LangGraph.

Orchestrates specialized agents for research, synthesis, critique, and refinement
to generate high-quality reports with iterative quality improvements.
"""

import json
import os
import sys
import threading
from typing import Any, Dict, List, TypedDict
from datetime import datetime

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from tavily import TavilyClient
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Make console output safe on Windows (cp1252) terminals when printing emoji/unicode
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Shared Groq LLM used by all LLM-powered agents (tool-calling capable)
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7,
)


# Live progress plumbing: lets UIs (React web app via FastAPI, CLI) receive
# stage-by-stage events. Stored on threading.local so concurrent sessions
# don't cross wires.
_progress_ctx = threading.local()


def _emit_progress(event: dict) -> None:
    """Send a progress event to the registered callback (if any). Never raises."""
    callback = getattr(_progress_ctx, "callback", None)
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        pass


def _response_text(response) -> str:
    """Extract plain text from a LangChain message response."""
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def _to_int_score(value, default: int = 5) -> int:
    """Coerce an LLM-returned score into a safe 0-10 int."""
    try:
        return max(0, min(10, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _serialize_review(review) -> dict | None:
    """Convert a CriticReview model into plain JSON-serializable data."""
    if review is None:
        return None
    return {
        "score": {
            "factual_accuracy": review.score.factual_accuracy,
            "completeness": review.score.completeness,
            "clarity": review.score.clarity,
            "structure": review.score.structure,
            "depth": review.score.depth,
            "average": round(review.score.average_score, 2),
        },
        "strengths": list(review.strengths),
        "weaknesses": list(review.weaknesses),
        "suggestions": list(review.suggestions),
        "pass_criteria_met": review.pass_criteria_met,
    }

# ============================================================================
# TYPE DEFINITIONS & STATE MANAGEMENT
# ============================================================================

class Source(BaseModel):
    """Represents a research source."""
    title: str
    url: str
    snippet: str
    content: str = ""


class ResearchData(BaseModel):
    """Container for research findings."""
    topic: str
    sources: List[Source]
    raw_content: str


class ReviewScore(BaseModel):
    """Quality evaluation metrics."""
    factual_accuracy: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)
    structure: int = Field(ge=0, le=10)
    depth: int = Field(ge=0, le=10)

    @property
    def average_score(self) -> float:
        """Calculate average score across all dimensions."""
        scores = [
            self.factual_accuracy,
            self.completeness,
            self.clarity,
            self.structure,
            self.depth,
        ]
        return sum(scores) / len(scores)


class CriticReview(BaseModel):
    """Structured critic evaluation output."""
    score: ReviewScore
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    pass_criteria_met: bool


class ReportState(TypedDict):
    """State dictionary for LangGraph workflow."""
    topic: str
    report_type: str  # academic, business, technical, news-style

    # Research phase
    research_data: ResearchData | None

    # Content generation phase
    draft_report: str | None

    # Critique phase
    critic_review: CriticReview | None

    # Refinement tracking
    iteration: int
    max_iterations: int
    refinement_history: List[Dict[str, Any]]

    # Final output
    final_report: str | None
    quality_threshold: float


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

class ResearchTools:
    """Tools for gathering and processing research data."""

    def __init__(self):
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    def web_search(self, query: str, num_results: int = 8) -> List[Source]:
        """
        Search the web using Tavily API.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of Source objects with URLs and snippets
        """
        try:
            response = self.tavily_client.search(
                query=query,
                max_results=num_results,
                include_raw_content=False,
            )

            sources = []
            for result in response.get("results", []):
                source = Source(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", ""),
                    content="",
                )
                sources.append(source)

            return sources
        except Exception as e:
            print(f"Error during web search: {e}")
            return []

    def scrape_url(self, url: str) -> str:
        """
        Extract clean body text from a URL.

        Args:
            url: URL to scrape

        Returns:
            Clean extracted text
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, timeout=10, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Extract text
            text = soup.get_text(separator=" ", strip=True)

            # Clean up excessive whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            return text[:3000]  # Limit to 3000 chars
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return ""


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================

class ResearchAgent:
    """Agent responsible for gathering comprehensive research data."""

    def __init__(self):
        self.tools = ResearchTools()

    def execute(self, state: ReportState) -> ReportState:
        """
        Execute research gathering phase.

        Searches the web and scrapes content from top sources.
        """
        print(f"\n🔍 RESEARCH AGENT: Gathering information on '{state['topic']}'")
        _emit_progress({"stage": "research", "status": "start", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": f"Searching the web for '{state['topic']}'"})

        # Search for relevant sources
        sources = self.tools.web_search(state["topic"], num_results=8)

        if not sources:
            print("⚠️ No sources found!")
            state["research_data"] = ResearchData(
                topic=state["topic"],
                sources=[],
                raw_content=""
            )
            _emit_progress({"stage": "research", "status": "done", "iteration": state["iteration"],
                            "max_iterations": state["max_iterations"], "message": "No sources found — using model knowledge", "sources": 0})
            return state

        # Scrape top 5 sources for deep content
        scraped_sources = []
        for i, source in enumerate(sources[:5]):
            print(f"  Scraping source {i+1}/5: {source.title[:50]}...")
            content = self.tools.scrape_url(source.url)
            source.content = content
            scraped_sources.append(source)

        # Combine all content
        raw_content = "\n\n".join([
            f"**{s.title}** ({s.url})\n{s.content}"
            for s in scraped_sources
        ])

        state["research_data"] = ResearchData(
            topic=state["topic"],
            sources=scraped_sources,
            raw_content=raw_content
        )

        print(f"✓ Gathered {len(scraped_sources)} sources with deep content")
        _emit_progress({"stage": "research", "status": "done", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": f"Gathered {len(scraped_sources)} sources", "sources": len(scraped_sources)})
        return state


class ContentSynthesizerAgent:
    """Agent that transforms raw research into coherent, structured reports."""

    def __init__(self):
        self.llm = llm

    def _get_system_prompt(self, report_type: str) -> str:
        """Get appropriate system prompt based on report type."""
        prompts = {
            "academic": """You are a world-class academic researcher and writer.
Your reports are rigorous, well-cited, and follow academic conventions.
Structure: Introduction | Literature Review | Key Findings | Analysis | Conclusion | References""",

            "business": """You are a strategic business consultant and report writer.
Your reports are executive-focused, actionable, and data-driven.
Structure: Executive Summary | Market Overview | Key Insights | Strategic Implications | Recommendations""",

            "technical": """You are a technical expert and documentation writer.
Your reports are detailed, precise, and implementation-focused.
Structure: Overview | Technical Details | Architecture | Best Practices | Recommendations""",

            "news-style": """You are a professional journalist and news analyst.
Your reports are engaging, well-paced, and lead with the most important information.
Structure: Lead | Context | Details | Impact | Expert Perspectives""",
        }

        return prompts.get(report_type, prompts["academic"])

    def execute(self, state: ReportState) -> ReportState:
        """Generate first-draft report from research data."""
        print(f"\n✍️ CONTENT SYNTHESIZER: Creating draft report")
        _emit_progress({"stage": "synthesize", "status": "start", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": "Writing the report draft..."})

        if not state.get("research_data"):
            state["draft_report"] = "No research data available."
            return state

        research = state["research_data"]

        # Prepare research context
        sources_summary = "\n".join([
            f"- {s.title}: {s.snippet[:200]}..."
            for s in research.sources
        ])

        user_prompt = f"""Write a comprehensive research report on: {state['topic']}

Available Research:
{research.raw_content[:4000]}

Source Summaries:
{sources_summary}

Requirements:
- Length: 800-1200 words
- Include proper citations with [Source: URL]
- Structure clearly with headers
- Be engaging and professional
- Go beyond surface-level information
"""

        response = self.llm.invoke([
            ("system", self._get_system_prompt(state.get("report_type", "academic"))),
            ("user", user_prompt),
        ])

        draft_report = _response_text(response)
        state["draft_report"] = draft_report

        print(f"✓ Draft report generated ({len(draft_report)} characters)")
        _emit_progress({"stage": "synthesize", "status": "done", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": "Draft ready"})
        return state


class CriticAgent:
    """Agent that rigorously evaluates reports on multiple dimensions."""

    def __init__(self):
        self.llm = llm

    def execute(self, state: ReportState) -> ReportState:
        """Evaluate report quality across 5 dimensions."""
        print(f"\n🧐 CRITIC AGENT: Evaluating report quality")
        _emit_progress({"stage": "critique", "status": "start", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": f"Critic reviewing report (iteration {state['iteration']})..."})

        if not state.get("draft_report"):
            state["critic_review"] = CriticReview(
                score=ReviewScore(factual_accuracy=0, completeness=0, clarity=0, structure=0, depth=0),
                strengths=[],
                weaknesses=["No report to review"],
                suggestions=[],
                pass_criteria_met=False
            )
            return state

        evaluation_prompt = f"""You are a strict critical editor. Evaluate this report on the following dimensions, each on a 0-10 scale:

1. Factual Accuracy: Are claims verifiable and properly cited?
2. Completeness: Does it address all important aspects of the topic?
3. Clarity & Readability: Is the writing clear, engaging, and well-structured?
4. Structure: Are sections logically organized with proper flow?
5. Depth: Does it go beyond surface-level information?

Report to Review:
---
{state['draft_report']}
---

Provide your evaluation in this exact JSON format:
{{
    "factual_accuracy": <0-10>,
    "completeness": <0-10>,
    "clarity": <0-10>,
    "structure": <0-10>,
    "depth": <0-10>,
    "strengths": ["strength1", "strength2", "strength3"],
    "weaknesses": ["weakness1", "weakness2", "weakness3"],
    "suggestions": ["suggestion1", "suggestion2", "suggestion3"]
}}

Only return valid JSON, no other text."""

        response = self.llm.invoke(evaluation_prompt)

        try:
            response_text = _response_text(response)
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                evaluation_data = json.loads(json_match.group())
            else:
                evaluation_data = json.loads(response_text)

            score = ReviewScore(
                factual_accuracy=_to_int_score(evaluation_data.get("factual_accuracy"), 0),
                completeness=_to_int_score(evaluation_data.get("completeness"), 0),
                clarity=_to_int_score(evaluation_data.get("clarity"), 0),
                structure=_to_int_score(evaluation_data.get("structure"), 0),
                depth=_to_int_score(evaluation_data.get("depth"), 0),
            )

            state["critic_review"] = CriticReview(
                score=score,
                strengths=evaluation_data.get("strengths", []),
                weaknesses=evaluation_data.get("weaknesses", []),
                suggestions=evaluation_data.get("suggestions", []),
                pass_criteria_met=score.average_score >= state["quality_threshold"]
            )

            _emit_progress({"stage": "critique", "status": "done", "iteration": state["iteration"],
                            "max_iterations": state["max_iterations"], "score": round(score.average_score, 2),
                            "message": f"Scored {score.average_score:.1f}/10"})
            print(f"✓ Report scored: {score.average_score:.1f}/10")
            print(f"  - Factual Accuracy: {score.factual_accuracy}/10")
            print(f"  - Completeness: {score.completeness}/10")
            print(f"  - Clarity: {score.clarity}/10")
            print(f"  - Structure: {score.structure}/10")
            print(f"  - Depth: {score.depth}/10")

        except Exception as e:
            print(f"Error parsing evaluation: {e}")
            _emit_progress({"stage": "critique", "status": "done", "iteration": state["iteration"],
                            "max_iterations": state["max_iterations"], "score": None,
                            "message": "Evaluation could not be parsed"})
            state["critic_review"] = CriticReview(
                score=ReviewScore(factual_accuracy=5, completeness=5, clarity=5, structure=5, depth=5),
                strengths=[],
                weaknesses=["Failed to parse evaluation"],
                suggestions=[],
                pass_criteria_met=False
            )

        return state


class RefinementAgent:
    """Agent that iteratively improves reports based on critic feedback."""

    def __init__(self):
        self.llm = llm

    def execute(self, state: ReportState) -> ReportState:
        """Refine report based on critic feedback."""
        print(f"\n🔄 REFINEMENT AGENT: Improving report (Iteration {state['iteration']})")
        _emit_progress({"stage": "refine", "status": "start", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": f"Refining report (iteration {state['iteration']} of {state['max_iterations']})..."})

        if not state.get("critic_review"):
            return state

        review = state["critic_review"]

        # Build refinement prompt with specific feedback
        refinement_prompt = f"""You are a professional editor tasked with improving a research report based on critical feedback.

Original Report:
---
{state['draft_report']}
---

Critic Feedback:
- Weaknesses: {', '.join(review.weaknesses)}
- Suggestions: {', '.join(review.suggestions)}
- Scores: Accuracy {review.score.factual_accuracy}/10, Completeness {review.score.completeness}/10, Clarity {review.score.clarity}/10, Structure {review.score.structure}/10, Depth {review.score.depth}/10

Your task:
1. Preserve the strengths mentioned: {', '.join(review.strengths)}
2. Directly address each weakness
3. Implement the specific suggestions
4. Improve the report to exceed a 7/10 quality threshold
5. Maintain 800-1200 words or expand if needed for completeness

Provide the refined report with clear improvements."""

        response = self.llm.invoke(refinement_prompt)

        refined_report = _response_text(response)

        # Track refinement in history
        state["refinement_history"].append({
            "iteration": state["iteration"],
            "timestamp": datetime.now().isoformat(),
            "previous_score": round(state["critic_review"].score.average_score, 2),
            "changes_made": state["critic_review"].suggestions,
        })

        state["draft_report"] = refined_report
        state["critic_review"] = None  # Reset for next evaluation
        state["iteration"] += 1

        print(f"✓ Report refined. Will re-evaluate in next iteration.")
        _emit_progress({"stage": "refine", "status": "done", "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"], "message": "Refinement applied — re-evaluating..."})
        return state


# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================

def should_continue_refinement(state: ReportState) -> str:
    """
    Determine if refinement should continue or stop.

    Returns: "refine" to continue, "finalize" to stop
    """
    review = state.get("critic_review")
    if not review:
        return "refine"  # Safety: never dead-end (refine loops back to critique)

    # Check pass criteria
    if review.pass_criteria_met:
        print(f"✅ Quality threshold met! (Score: {review.score.average_score:.1f}/10)")
        return "finalize"

    # Check max iterations
    if state["iteration"] >= state["max_iterations"]:
        print(f"⚠️ Max iterations ({state['max_iterations']}) reached.")
        return "finalize"

    return "refine"


def create_report_generation_workflow() -> StateGraph:
    """Create the LangGraph workflow for report generation."""

    # Initialize agents
    research_agent = ResearchAgent()
    synthesizer_agent = ContentSynthesizerAgent()
    critic_agent = CriticAgent()
    refinement_agent = RefinementAgent()

    # Create graph
    workflow = StateGraph(ReportState)

    # Add nodes
    workflow.add_node("research", research_agent.execute)
    workflow.add_node("synthesize", synthesizer_agent.execute)
    workflow.add_node("critique", critic_agent.execute)
    workflow.add_node("refine", refinement_agent.execute)
    workflow.add_node("finalize", lambda state: state)

    # Add edges
    workflow.add_edge(START, "research")
    workflow.add_edge("research", "synthesize")
    workflow.add_edge("synthesize", "critique")

    # Conditional edge based on quality
    workflow.add_conditional_edges(
        "critique",
        should_continue_refinement,
        {
            "refine": "refine",  # Route to the refinement agent (which edges back to critique)
            "finalize": "finalize",
        }
    )

    workflow.add_edge("refine", "critique")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def generate_report(
    topic: str,
    report_type: str = "academic",
    quality_threshold: float = 7.0,
    max_iterations: int = 4,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Generate a high-quality research report through multi-agent orchestration.

    Args:
        topic: Research topic
        report_type: Type of report (academic, business, technical, news-style)
        quality_threshold: Minimum quality score (0-10) to consider report complete
        max_iterations: Maximum refinement iterations allowed

    Returns:
        Dictionary with final report, evaluation, and generation metadata
    """

    # Initialize state
    initial_state: ReportState = {
        "topic": topic,
        "report_type": report_type,
        "research_data": None,
        "draft_report": None,
        "critic_review": None,
        "iteration": 1,
        "max_iterations": max_iterations,
        "refinement_history": [],
        "final_report": None,
        "quality_threshold": quality_threshold,
    }

    # Create and run workflow
    print(f"\n{'='*70}")
    print(f"🚀 STARTING MULTI-AGENT REPORT GENERATION")
    print(f"{'='*70}")
    print(f"Topic: {topic}")
    print(f"Report Type: {report_type}")
    print(f"Quality Threshold: {quality_threshold}/10")
    print(f"Max Iterations: {max_iterations}")

    _progress_ctx.callback = progress_callback
    try:
        _emit_progress({"stage": "start", "status": "start", "iteration": 1,
                        "max_iterations": max_iterations, "message": "Starting multi-agent pipeline..."})
        workflow = create_report_generation_workflow()
        final_state = workflow.invoke(initial_state)
    except Exception as e:
        _emit_progress({"stage": "error", "status": "error", "iteration": None,
                        "max_iterations": max_iterations, "message": str(e)})
        raise
    finally:
        _progress_ctx.callback = None

    # Prepare output
    result = {
        "topic": topic,
        "report_type": report_type,
        "final_report": final_state.get("draft_report"),
        "final_score": round(final_state["critic_review"].score.average_score, 2) if final_state.get("critic_review") else None,
        "iterations_completed": final_state["iteration"] - 1,
        "quality_threshold_met": final_state["critic_review"].pass_criteria_met if final_state.get("critic_review") else False,
        "final_review": _serialize_review(final_state.get("critic_review")),
        "refinement_history": final_state["refinement_history"],
        "timestamp": datetime.now().isoformat(),
    }

    print(f"\n{'='*70}")
    print(f"✨ REPORT GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"Final Score: {result['final_score']}/10")
    print(f"Iterations: {result['iterations_completed']}")
    print(f"Quality Threshold Met: {result['quality_threshold_met']}")

    _emit_progress({"stage": "done", "status": "done", "iteration": result["iterations_completed"],
                    "max_iterations": max_iterations, "score": result["final_score"],
                    "threshold_met": result["quality_threshold_met"],
                    "message": f"Report complete — final score {result['final_score']}/10"})

    return result


if __name__ == "__main__":
    # Example usage
    topic = input("Enter research topic: ").strip()
    report_type = input("Enter report type (academic/business/technical/news-style) [academic]: ").strip() or "academic"

    result = generate_report(
        topic=topic,
        report_type=report_type,
        quality_threshold=7.0,
        max_iterations=4,
    )

    # Save report to file
    output_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(output_filename, "w") as f:
        f.write(result["final_report"])

    print(f"\n📄 Report saved to: {output_filename}")
    print(f"\nFinal Score: {result['final_score']}/10")
    print(f"Quality Threshold Met: {result['quality_threshold_met']}")
