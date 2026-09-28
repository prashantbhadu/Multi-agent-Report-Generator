# 🤖 Multi-Agent Report Generator

An autonomous research orchestration system built on **LangGraph** that generates high-quality, well-researched reports on ANY topic through intelligent multi-agent collaboration — with a **React** frontend and a **FastAPI** backend.

## 🌟 Key Features

- **👤 User Accounts** — Email + password signup/login with JWT sessions (7-day tokens)
- **🧭 Supervisor Orchestration** — A supervisor agent plans the run, then after the final report decides whether to invoke the Email Agent
- **📧 Email MCP Server** — Email capabilities exposed as Model Context Protocol tools: `send_email`, `create_draft`, `send_draft`, `list_messages`, `get_message`
- **🤖 Email Agent** — Reasons about recipient/subject/body, then calls the `send_email()` MCP tool to deliver the report (Gmail when connected, local outbox otherwise)
- **🔍 Research Agent** — Autonomously gathers comprehensive information via Tavily web search and deep content scraping with BeautifulSoup4
- **✍️ Content Synthesizer Agent** — Transforms raw research into coherent, professionally-structured reports with multiple style options
- **🧐 Critic Agent** — Rigorously evaluates reports across 5 quality dimensions (factual accuracy, completeness, clarity, structure, depth)
- **🔄 Refinement Agent** — Iteratively improves reports based on critic feedback until quality threshold is met
- **⚛️ React Web UI** — Interactive frontend with live pipeline visualization, evaluation dashboard, and history management
- **🚀 FastAPI Backend** — REST API with Server-Sent Events (SSE) for real-time progress streaming
- **💻 CLI Interface** — Full command-line control with JSON export and batch processing
- **✅ Intelligent Workflow** — LangGraph-powered orchestration with conditional routing and state management

## 🏗️ System Architecture

```
┌─────────────────┐
│  User request   │  (+ optional "email when done")
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Supervisor          │  ← plans the agent pipeline
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Research Agent      │  ← Web Search + Deep Scraping
│  (Tavily + BS4)      │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Content Synthesizer  │  ← LLM Report Writing
│ (Report Generation)  │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Critic Agent        │  ← Quality Evaluation (5 dimensions)
│  (Quality Review)    │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Quality Check       │  ← pass / fail / max-iterations gate
└────────┬─────────────┘
         │
    ┌────▼──────────┐
    │ Pass Quality? │
    │   (≥7/10)     │
    └────┬────┬─────┘
         │    │
      YES│    │NO (max 4 iterations)
         │    │
         │    ▼
         │ ┌──────────────────────┐
         │ │ Refinement Agent     │  ← loops back to the Critic
         │ └──────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Final Report        │
└────────┬─────────────┘
         │
         ▼
┌───────────────────────────────────────────┐
│  Supervisor decides                       │
│  "User requested email → invoke Email     │
│   Agent" (else finish)                    │
└────────┬──────────────────────────────────┘
         │
         ▼
┌──────────────────────┐     ┌────────────────────────────┐
│  Email Agent         │ ──► │  Email MCP Server          │
│  (reasons: recipient,│     │  ├ send_email        ◄─┐   │
│   subject, body)     │     │  ├ create_draft         │   │
└──────────────────────┘     │  ├ send_draft           │   │
                             │  ├ list_messages        │   │
                             │  └ get_message          │   │
                             └─────────┬──────────────┘   │
                                       │  MCP tool call   │
                                       └──────────────────┘
                                              │
                                              ▼
                                        Recipient
```

### Web Application Architecture

```
┌────────────────────┐         ┌─────────────────────┐
│  React Frontend    │  HTTP   │  FastAPI Backend    │
│  (Vite, port 5173) │◄───────►│  (uvicorn, :8000)   │
│                    │  SSE    │                     │
│  • Home            │         │  • POST /generate   │
│  • History         │         │  • GET  /jobs/*/events (SSE)
│  • Settings        │         │  • GET  /reports    │
└────────────────────┘         └──────────┬──────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │  LangGraph Pipeline │
                               │  (report_generator) │
                               └─────────────────────┘
```

## 📂 Project Structure

```
Multi-agent-AI/
├── frontend/                 # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx           # App shell + auth gate + sidebar navigation
│   │   ├── Auth.tsx          # Login / signup page
│   │   ├── Home.tsx          # Generation form + live pipeline + results + email sending
│   │   ├── History.tsx       # Reports browser + sent-email history (tabs)
│   │   ├── Settings.tsx      # Gmail connection + configuration status
│   │   ├── api.ts            # Typed API client (JWT handling, SSE subscription)
│   │   └── index.css         # Dark theme styling
│   └── index.html
│
├── api.py                    # FastAPI backend
│                             # - POST /api/auth/signup, /api/auth/login (JWT)
│                             # - GET  /api/gmail/authorize, /api/gmail/callback (OAuth2)
│                             # - POST /api/gmail/send, GET /api/emails (history)
│                             # - POST /api/generate (start job)
│                             # - GET  /api/jobs/{id}/events (SSE progress)
│                             # - GET  /api/reports (history)
│
├── auth.py                   # JWT issuance/verification + password hashing
├── database.py               # SQLite persistence (users, gmail tokens, email history, drafts)
├── gmail_service.py          # Gmail OAuth2 flow + report emailing
│
├── email_mcp_server.py       # Email MCP server (stdio / streamable-http)
│                             #   tools: send_email, create_draft, send_draft,
│                             #          list_messages, get_message
├── email_mcp_client.py       # Sync stdio client used by the pipeline + API
│
├── report_generator.py       # Core LangGraph orchestration system
│                             # - Research, Synthesizer, Critic, Refinement agents
│                             # - Workflow graph management
│                             # - State definitions and types
│
├── cli.py                    # Command-line interface
│                             # - Batch report generation
│                             # - JSON export capabilities
│                             # - Full parameter control
│
├── tools.py                  # Legacy tool definitions (LangChain)
├── agents.py                 # Legacy agent setup
├── app.py                    # Legacy interface
├── pipeline.py               # Legacy orchestration
│
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (API keys)
├── .gitignore
└── README.md                 # This file
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | React 19 + TypeScript + Vite | Interactive web UI |
| **Backend API** | FastAPI + Uvicorn | REST API + SSE progress streaming |
| **Orchestration** | LangGraph | Multi-agent workflow management |
| **LLM** | Groq (`openai/gpt-oss-120b`) | Report generation & evaluation |
| **Search** | Tavily API | Web research & source discovery |
| **Web Scraping** | BeautifulSoup4 + Requests | Deep content extraction |
| **CLI** | Python argparse | Command-line interface |
| **Data Handling** | Pydantic | Type-safe state management |
| **Environment** | python-dotenv | API key configuration |
| **Auth** | PyJWT + pbkdf2 | User accounts and session tokens |
| **Database** | SQLite | Users, Gmail tokens, sent-email history |
| **Email** | MCP server (stdio) + Gmail API | Email Agent tool calls, OAuth2 delivery |

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the React frontend)
- **Groq API Key** — [Get one here](https://console.groq.com/keys)
- **Tavily API Key** — [Get one here](https://tavily.com/)

### 2. Backend Setup

```bash
# Clone the repository
git clone <repository-url>
cd Multi-agent-AI

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

> 🔑 **Environment files are NOT tracked by git** — they are git-ignored for
> your security. Copy `.env.example` (if provided) or create `.env` manually.

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Session signing (any long random string; required in production)
JWT_SECRET=change-me-to-a-long-random-string

# Optional: Gmail emailing (Settings → Connect Gmail)
# Create credentials at https://console.cloud.google.com
# (APIs & Services -> Credentials -> OAuth client ID, type: Web application)
# and enable the Gmail API. Authorised redirect URI:
#   http://localhost:8000/api/gmail/callback
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GMAIL_REDIRECT_URI=http://localhost:8000/api/gmail/callback
```

> ⚠️ **Google verification warning:** Your app requests the restricted scope
> `https://mail.google.com/`, so Google places it in **Testing** mode. Until you
> publish the app on Google Cloud, only developer-approved testers (e.g. your
> own Gmail address added under **OAuth consent screen → Test users**) can use
> it. To test locally, add your Gmail address as a test user. If you switch the
> scope in `gmail_service.py` to
> `https://www.googleapis.com/auth/gmail.send`, it works without test-user
> approval.

### 3. Frontend Setup

```bash
# In a new terminal, from the project root
cd frontend
npm install
```

### 4. Run the App

**Terminal 1 — Backend API:**

```bash
# From the project root (with venv activated)
uvicorn api:app --reload --port 8000
```

**Terminal 2 — React frontend:**

```bash
# From the frontend/ directory
npm run dev
```

Then open **http://localhost:5173** in your browser.

## 💻 Usage

### Accounts & Gmail Emailing

1. Open http://localhost:5173 and **sign up** (email + password, min 8 chars) — you're logged in immediately
2. (Optional) Go to **Settings → Connect Gmail** and complete the Google consent screen to enable report emailing
3. After generating a report, click **✉️ Email report** in the results to send it to any address
4. Every sent email appears in **History → Emails**

> Without Google OAuth credentials configured, the Connect Gmail button will report that Gmail isn't configured. Generation, history, and downloads work fine without it.

### Supervisor → Email Agent (MCP) Flow

1. On the Generate page, tick **📧 Email the finished report** and set a recipient (defaults to your own address)
2. The **Supervisor** plans the run, then the normal pipeline executes:
   Research → Synthesizer → Critic → Quality Check → (Refine loop)
3. After the **Final Report**, the Supervisor decides: *"User requested email → invoke Email Agent"*
4. The **Email Agent** reasons about recipient/subject/body and calls the `send_email()` MCP tool
5. The result ("sent" via Gmail, or "local" outbox fallback) appears in the results header and in **History → Emails**

### Email MCP Server

Email capabilities are exposed as MCP tools by `email_mcp_server.py`:

| Tool | Description |
|------|-------------|
| `send_email(to, subject, body, …)` | Send an email (Gmail API, else local outbox) |
| `create_draft(to, subject, body, …)` | Create a draft (mirrored to Gmail drafts when connected) |
| `send_draft(draft_id, …)` | Deliver a stored draft |
| `list_messages(query?, …)` | List recent messages (Gmail inbox or local outbox) |
| `get_message(message_id, …)` | Fetch one message or draft by id |

Run it standalone for external MCP hosts:

```bash
# stdio (used by the pipeline via email_mcp_client.py)
python email_mcp_server.py

# streamable HTTP, e.g. for Claude Desktop / MCP inspectors
python email_mcp_server.py --http 8001
```

Then in your MCP host config:

```json
{
  "mcpServers": {
    "reportforge-email": {
      "command": ".venv/Scripts/python.exe",
      "args": ["email_mcp_server.py"]
    }
  }
}
```

### Web Interface (React + FastAPI)

1. Open http://localhost:5173
2. Enter a topic and select a report type (academic, business, technical, news-style)
3. Click **🚀 Generate Report**
4. Watch the live pipeline visualization — quality threshold (≥ 7.0/10) and the
   refinement loop (max 4 iterations) are managed automatically in the background
5. Review results in the tabbed dashboard (Report, Evaluation, Iteration Loop, Metadata)
6. Download the report as Markdown or export the evaluation as JSON
7. Browse, download, or delete past reports from the **History** page

### Backend API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Create an account → `{ token, user }` |
| `POST` | `/api/auth/login` | Log in → `{ token, user }` |
| `GET` | `/api/auth/me` | Current user + Gmail connection state |
| `GET` | `/api/gmail/authorize` | Start Gmail OAuth2 (redirects to Google) |
| `GET` | `/api/gmail/callback` | OAuth2 redirect target (stores tokens) |
| `GET` | `/api/gmail/status` | Whether Gmail is connected |
| `POST` | `/api/gmail/send` | Email a report via the connected Gmail |
| `GET` | `/api/emails` | Sent-email history |
| `GET` | `/api/config` | Fixed run parameters (threshold, max iterations) |
| `POST` | `/api/generate` | Start a generation job (`email_requested`, `email_recipient` supported) → `{ job_id }` |
| `GET` | `/api/jobs/{id}/events` | SSE stream of live pipeline progress |
| `GET` | `/api/jobs/{id}` | Final result (404 until the job finishes) |

> All endpoints except `signup`/`login` require an `Authorization: Bearer <token>` header (7-day JWT issued at signup/login).
| `GET` | `/api/reports` | List saved reports (newest first) |
| `GET` | `/api/reports/{name}` | Download a saved report |
| `DELETE` | `/api/reports/{name}` | Delete a saved report |

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
--max-iterations INT     Max refinement loops (default: 4)
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
    max_iterations=4,
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

1. **Factual Accuracy (0-10)** — Are claims verifiable, cited, and up-to-date?
2. **Completeness (0-10)** — Does it address all important aspects of the topic?
3. **Clarity & Readability (0-10)** — Is the writing clear, engaging, and accessible?
4. **Structure (0-10)** — Are sections logically organized with natural flow?
5. **Depth (0-10)** — Does it go beyond surface-level with nuanced analysis?

**Passing Criteria:** Average score ≥ quality threshold (default: 7.0/10)

## 🔄 Refinement Process

1. **Initial Synthesis** — Content Synthesizer generates first draft
2. **Critique** — Critic Agent evaluates across 5 dimensions
3. **Decision** — Check if quality threshold is met
   - ✅ **Pass** → Report finalized
   - ❌ **Fail** → Enter refinement loop (max 4 iterations)
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

| Type | Structure | Style | Best For |
|------|-----------|-------|----------|
| **🎓 Academic** | Introduction \| Literature Review \| Key Findings \| Analysis \| Conclusion \| References | Rigorous, well-cited, formal tone | Research papers, scholarly analysis |
| **💼 Business** | Executive Summary \| Market Overview \| Key Insights \| Strategic Implications \| Recommendations | Executive-focused, data-driven, actionable | Market analysis, strategic reports |
| **🛠️ Technical** | Overview \| Technical Details \| Architecture \| Best Practices \| Recommendations | Detailed, precise, implementation-focused | Technical documentation, system analysis |
| **📰 News-Style** | Lead \| Context \| Details \| Impact \| Expert Perspectives | Engaging, well-paced, journalistic | News analysis, trend reports, current events |

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
  "timestamp": "2026-09-23T06:44:23.804Z",
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
    "strengths": ["..."],
    "weaknesses": ["..."],
    "suggestions": ["..."]
  }
}
```

## 🔐 Security & Best Practices

- **API Keys:** Store in `.env` file, never commit to version control
- **CORS:** The API only accepts browser origins from localhost (dev ports 5173/4173)
- **Sensitive files — git-ignored** (see `.gitignore`):

  | File | Why it is ignored |
  |------|-------------------|
  | `.env` / `.env.local` | Holds `GOOGLE_CLIENT_SECRET`, `GROQ_API_KEY`, `JWT_SECRET` — credentials that would compromise your Google Cloud project and sessions if exposed |
  | `app.db` | Local SQLite database containing user accounts, Gmail refresh tokens, and sent-email history |
  | `frontend/node_modules/` | Third-party packages (reinstall with `npm install` on a fresh clone) |

> If you ever commit a `.env` by accident, rotate the exposed secrets
> immediately and remove the file from history with `git filter-repo` or
> `git filter-branch`.

- **Gmail OAuth:** Your app requests the restricted scope
  `https://mail.google.com/`, so Google puts it in **Testing** mode. Add your
  email as a **Test User** under **OAuth consent screen → Test users** until you
  publish the app. See the note in the [Gmail OAuth setup](#Gmail-OAuth) section.
- **Sensitive files — git-ignored** (see `.gitignore`):

  | File | Why it is ignored |
  |------|-------------------|
  | `.env` / `.env.local` | Holds `GOOGLE_CLIENT_SECRET`, `GROQ_API_KEY`, `JWT_SECRET` — credentials that would compromise your Google Cloud project and sessions if exposed |
  | `app.db` | Local SQLite database containing user accounts, Gmail refresh tokens, and sent-email history |
  | `frontend/node_modules/` | Third-party packages (reinstall with `npm install` on a fresh clone) |

> If you ever commit a `.env` by accident, rotate the exposed secrets
> immediately and remove the file from history with `git filter-repo` or
> `git filter-branch`.

- **Gmail OAuth:** Your app requests the restricted scope
  `https://mail.google.com/`, so Google puts it in **Testing** mode. Add your
  email as a **Test User** under **OAuth consent screen → Test users** until you
  publish the app. See the note in the [Gmail OAuth setup](#Gmail-OAuth) section.
- **Rate Limiting:** Tavily and Groq APIs have rate limits
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

### Frontend shows "Connection refused" or Settings shows "Offline"

- Make sure the FastAPI backend is running: `uvicorn api:app --port 8000`
- Check the backend terminal for startup errors (missing API keys, etc.)

### "Web search returned no results"

- Topic may be too specific or niche
- Try a broader search term
- Check internet connection

### "Report quality stuck below threshold"

- Increase `max_iterations` (edit `MAX_ITERATIONS` in `api.py`)
- Lower `quality_threshold` (edit `QUALITY_THRESHOLD` in `api.py`)
- Topic may have limited available information

### Port already in use

```bash
# Backend on a different port
uvicorn api:app --port 8001
# (then update the API base URL in frontend/src/api.ts)

# Frontend on a different port
cd frontend && npm run dev -- --port 5174
```

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
  --max-iterations 4 \
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

---

Built with LangGraph, Groq, Tavily, FastAPI, and React.
