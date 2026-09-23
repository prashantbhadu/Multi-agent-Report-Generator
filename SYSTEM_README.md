# 🤖 Advanced Multi-Agent Report Generation System

An autonomous, state-of-the-art research orchestration system built on **LangGraph** that generates high-quality, well-researched reports on ANY topic through intelligent multi-agent collaboration.

## 🌟 Key Features

- **🔍 Research Agent** — Autonomously gathers comprehensive information via Tavily web search and deep content scraping with BeautifulSoup4
- **✍️ Content Synthesizer Agent** — Transforms raw research into coherent, professionally-structured reports with multiple style options
- **🧐 Critic Agent** — Rigorously evaluates reports across 5 quality dimensions (factual accuracy, completeness, clarity, structure, depth)
- **🔄 Refinement Agent** — Iteratively improves reports based on critic feedback until quality threshold is met
- **📊 Streamlit Web UI** — Interactive dashboard for report generation, evaluation visualization, and history management
- **💻 CLI Interface** — Full command-line control with JSON export and batch processing
- **✅ Intelligent Workflow** — LangGraph-powered orchestration with conditional routing and state management

## 🏗️ System Architecture

```
┌─────────────────┐
│   User Input    │
│   (Topic Type)  │
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Research Agent      │  ← Web Search + Deep Scraping
│  (Tavily + BS4)      │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Content Synthesizer  │  ← Claude AI Report Writing
│ (Report Generation)  │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Critic Agent        │  ← Quality Evaluation (5 dimensions)
│  (Quality Review)    │
└────────┬─────────────┘
         │
    ┌────▼──────────┐
    │ Pass Quality? │
    │   (≥7/10)     │
    └────┬────┬─────┘
         │    │
      YES│    │NO (max 6 iterations)
         │    │
         │    ▼
         │ ┌──────────────────────┐
         │ │ Refinement Agent     │  ← Iterative Improvements
         │ │ (Apply Feedback)     │
         │ └────────┬─────────────┘
         │          │
         │          └──────┐
         │                 │ (Re-evaluate)
         │          ┌──────▼─────┐
         │          │ Critic     │
         │          │ Re-review  │
         │          └──────┬─────┘
         │                 │
         └────────┬────────┘
                  │
                  ▼
         ┌──────────────────┐
         │  Final Report    │
         │  + Evaluation    │
         └──────────────────┘
```

## 📂 Project Structure

```
Multi-agent-AI/
├── report_generator.py      # Core LangGraph orchestration system
│                            # - Research, Synthesizer, Critic, Refinement agents
│                            # - Workflow graph management
│                            # - State definitions and types
│
├── streamlit_app.py         # Web UI with Streamlit
│                            # - Interactive report generation
│                            # - Quality evaluation dashboard
│                            # - Report history management
│
├── cli.py                   # Command-line interface
│                            # - Batch report generation
│                            # - JSON export capabilities
│                            # - Full parameter control
│
├── tools.py                 # Legacy tool definitions (LangChain)
├── agents.py                # Legacy agent setup
├── app.py                   # Legacy Streamlit interface
├── pipeline.py              # Legacy orchestration
│
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (API keys)
├── .gitignore
└── README.md                # This file
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestration** | LangGraph | Multi-agent workflow management |
| **LLM** | Claude 3.5 Sonnet (Anthropic) | Report generation & evaluation |
| **Search** | Tavily API | Web research & source discovery |
| **Web Scraping** | BeautifulSoup4 + Requests | Deep content extraction |
| **Web UI** | Streamlit | Interactive dashboard |
| **CLI** | Python argparse | Command-line interface |
| **Data Handling** | Pydantic | Type-safe state management |
| **Environment** | python-dotenv | API key configuration |

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+**
- **Anthropic API Key** — [Get one here](https://console.anthropic.com/)
- **Tavily API Key** — [Get one here](https://tavily.com/)

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd Multi-agent-AI

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

## 💻 Usage

### Web Interface (Streamlit)

```bash
streamlit run streamlit_app.py
```

Then open http://localhost:8501 in your browser.

**Features:**
- 📝 Enter topic and select report type (academic, business, technical, news-style)
- ⚙️ Configure quality threshold and max iterations
- 📊 Real-time progress tracking
- 📈 Interactive evaluation dashboard with dimension scores
- 📚 Full refinement history visualization
- 📥 Download reports in Markdown format

### Command-Line Interface

```bash
# Basic usage
python cli.py --topic "Quantum Computing Advances"

# With custom parameters
python cli.py \
  --topic "AI Market Trends" \
  --type business \
  --threshold 8.0 \
  --max-iterations 5 \
  --verbose

# Save as JSON metadata
python cli.py --topic "Climate Change" --json --verbose

# List all options
python cli.py --help
```

**CLI Options:**
```
--topic TEXT              Research topic (required)
--type {academic,business,technical,news-style}
                         Report type (default: academic)
--threshold FLOAT        Quality threshold 0-10 (default: 7.0)
--max-iterations INT     Max refinement loops (default: 6)
--output PATH            Output directory (default: ./reports/)
--verbose, -v            Enable verbose output
--json                   Export JSON metadata
--no-save                Skip saving to file
```

### Programmatic Usage

```python
from report_generator import generate_report

# Generate a report
result = generate_report(
    topic="Artificial Intelligence in Healthcare",
    report_type="technical",
    quality_threshold=7.5,
    max_iterations=6,
)

# Access results
print(f"Final Score: {result['final_score']}/10")
print(f"Quality Met: {result['quality_threshold_met']}")
print(f"Report:\n{result['final_report']}")
print(f"Iterations: {result['iterations_completed']}")
print(f"Feedback: {result['final_review']}")
```

## 📊 Quality Evaluation Framework

Reports are evaluated on **5 key dimensions**:

1. **Factual Accuracy (0-10)**
   - Are claims verifiable?
   - Are sources properly cited?
   - Is information up-to-date?

2. **Completeness (0-10)**
   - Does it address all aspects?
   - Are important points covered?
   - Is scope appropriate?

3. **Clarity & Readability (0-10)**
   - Is writing clear and engaging?
   - Is technical content accessible?
   - Is structure easy to follow?

4. **Structure (0-10)**
   - Are sections logically organized?
   - Is flow natural?
   - Do transitions work well?

5. **Depth (0-10)**
   - Goes beyond surface-level?
   - Provides meaningful insights?
   - Includes nuanced analysis?

**Passing Criteria:** Average score ≥ quality threshold (default: 7.0/10)

## 🔄 Refinement Process

The system iteratively improves reports through a feedback loop:

1. **Initial Synthesis** — Content Synthesizer generates first draft
2. **Critique** — Critic Agent evaluates across 5 dimensions
3. **Decision** — Check if quality threshold is met
   - ✅ **Pass** → Report finalized
   - ❌ **Fail** → Enter refinement loop (max 6 iterations)
4. **Refinement** — Refinement Agent addresses weaknesses
5. **Re-evaluation** — Critic re-evaluates improved report
6. **Repeat** — Steps 3-5 until pass or max iterations reached

**Example Output:**
```
Iteration 1: Score 6.2/10 → Needs refinement
Iteration 2: Score 6.8/10 → Still below threshold
Iteration 3: Score 7.4/10 → ✅ Quality threshold met!
```

## 📄 Report Types

### Academic
- **Structure:** Introduction | Literature Review | Key Findings | Analysis | Conclusion | References
- **Style:** Rigorous, well-cited, formal tone
- **Best for:** Research papers, scholarly analysis

### Business
- **Structure:** Executive Summary | Market Overview | Key Insights | Strategic Implications | Recommendations
- **Style:** Executive-focused, data-driven, actionable
- **Best for:** Market analysis, strategic reports, business intelligence

### Technical
- **Structure:** Overview | Technical Details | Architecture | Best Practices | Recommendations
- **Style:** Detailed, precise, implementation-focused
- **Best for:** Technical documentation, system analysis, architecture reports

### News-Style
- **Structure:** Lead | Context | Details | Impact | Expert Perspectives
- **Style:** Engaging, well-paced, journalistic
- **Best for:** News analysis, trend reports, current events

## 📈 Output & Artifacts

### Markdown Reports
```markdown
# Research Report

**Topic:** [Topic Name]
**Report Type:** [academic/business/technical/news-style]
**Generated:** [Timestamp]
**Quality Score:** 7.5/10

---

[Full Report Content]

---

## Generation Metadata
- **Iterations:** 3
- **Quality Threshold Met:** Yes
- **Final Review:** [JSON with scores and feedback]
```

### JSON Metadata
```json
{
  "topic": "...",
  "report_type": "academic",
  "timestamp": "2024-09-23T06:44:23.804Z",
  "final_score": 7.5,
  "quality_threshold_met": true,
  "iterations_completed": 3,
  "final_review": {
    "score": {
      "factual_accuracy": 8,
      "completeness": 7,
      "clarity": 8,
      "structure": 7,
      "depth": 8,
      "average": 7.6
    },
    "strengths": [...],
    "weaknesses": [...],
    "suggestions": [...]
  }
}
```

## 🔐 Security & Best Practices

- **API Keys:** Store in `.env` file, never commit to version control
- **Rate Limiting:** Tavily and Anthropic APIs have rate limits
- **Timeout:** Web scraping has 10-second timeout per URL
- **Content Limits:** Deep content capped at 3000 chars per source
- **Error Handling:** Graceful fallbacks for failed operations

## 🐛 Troubleshooting

### "API Key not found"
```bash
# Check .env file exists in project root
ls -la .env

# Verify keys are set correctly
cat .env
```

### "Web search returned no results"
- Topic may be too specific or niche
- Try a broader search term
- Check internet connection

### "Report quality stuck below threshold"
- Increase `max_iterations` (up to 10)
- Lower `quality_threshold` (minimum 5.0)
- Topic may have limited available information

### "Script hangs or times out"
- May be scraping slow websites
- Try again (transient network issues)
- Reduce `max_iterations` to see partial results faster

## 📚 Examples

### Example 1: Academic Report
```bash
python cli.py \
  --topic "Recent Breakthroughs in CRISPR Gene Editing" \
  --type academic \
  --threshold 8.0 \
  --verbose
```

### Example 2: Business Analysis
```bash
python cli.py \
  --topic "Competitive Landscape of Electric Vehicle Market" \
  --type business \
  --threshold 7.5 \
  --max-iterations 8 \
  --json
```

### Example 3: Technical Deep Dive
```bash
python cli.py \
  --topic "Kubernetes Architecture and Best Practices" \
  --type technical \
  --threshold 7.0 \
  --verbose
```

## 🤝 Contributing

Contributions are welcome! Areas for enhancement:

- Additional search backends (Google Scholar, arXiv)
- More LLM providers (GPT-4, Gemini)
- Report format exports (PDF, DOCX)
- Caching and result persistence
- Multi-language support
- Custom evaluation rubrics

## 📄 License

MIT License — See LICENSE file for details

## 🎓 Citation

If you use this system in research, please cite:

```bibtex
@software{multiagent_report_2024,
  title={Advanced Multi-Agent Report Generation System},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/Multi-agent-AI}
}
```

## 📞 Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check troubleshooting section above
- Review API documentation for Anthropic and Tavily

---

**Built with ❤️ using LangGraph, Claude AI, and Python**
