"""
Quick Start Guide for Multi-Agent Report Generator

This guide helps you get up and running in 5 minutes.
"""

# ============================================================================
# SETUP (First Time)
# ============================================================================

## Step 1: Get API Keys

# 1a. Anthropic API Key
#    - Go to https://console.anthropic.com/
#    - Sign up or log in
#    - Create new API key
#    - Copy the key

# 1b. Tavily API Key
#    - Go to https://tavily.com/
#    - Sign up for free
#    - Get your API key from dashboard

## Step 2: Create .env File

# In project root, create `.`.env` with:
# 
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
# TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx


## Step 3: Install Dependencies

# bash:
# pip install -r requirements.txt

# or install specific missing packages:
# pip install langgraph anthropic streamlit-option-menu


# ============================================================================
# QUICK START EXAMPLES
# ============================================================================

# --- Example 1: Web UI (Easiest) ---
# bash:
# streamlit run streamlit_app.py
#
# Then:
# 1. Open browser to http://localhost:8501
# 2. Enter topic (e.g., "Quantum Computing Advances")
# 3. Select report type (Academic, Business, Technical, News-style)
# 4. Click "Generate Report"
# 5. Watch real-time progress and get results with quality scores


# --- Example 2: CLI (Simple) ---
# bash:
# python cli.py --topic "AI in Healthcare" --type technical --verbose
#
# Options:
# --topic TEXT              The research topic (required)
# --type {academic,business,technical,news-style}  Report style
# --threshold FLOAT         Quality target 0-10 (default: 7.0)
# --max-iterations INT      Max refinement loops (default: 6)
# --verbose, -v            Show detailed output
# --json                   Also save JSON metadata
# --output PATH            Where to save files (default: ./reports/)


# --- Example 3: Python Script ---

from report_generator import generate_report

# Generate a report programmatically
result = generate_report(
    topic="Machine Learning in Drug Discovery",
    report_type="academic",
    quality_threshold=7.5,
    max_iterations=6,
)

# Check results
print(f"Score: {result['final_score']}/10")
print(f"Success: {result['quality_threshold_met']}")
print(f"Report:\n{result['final_report']}")

# Save to file
with open("my_report.md", "w") as f:
    f.write(result['final_report'])


# ============================================================================
# WHAT HAPPENS BEHIND THE SCENES
# ============================================================================

# When you run a report generation, the system:
#
# 1. RESEARCH PHASE
#    - Searches web via Tavily API for top 8 sources
#    - Scrapes top 5 sources using BeautifulSoup4
#    - Collects ~3000 chars of content per source
#
# 2. SYNTHESIS PHASE
#    - Sends research + topic to Claude AI (Anthropic)
#    - Claude writes 800-1200 word structured report
#    - Matches report type style (academic/business/etc)
#
# 3. CRITIQUE PHASE
#    - Sends report to Claude for evaluation
#    - Scores on 5 dimensions (0-10 each):
#      • Factual Accuracy - Are claims verified?
#      • Completeness - All aspects covered?
#      • Clarity - Is it well-written?
#      • Structure - Logical organization?
#      • Depth - Goes beyond surface?
#
# 4. QUALITY CHECK
#    - Calculates average score across 5 dimensions
#    - If score ≥ threshold (default 7.0):
#      → Report is DONE ✅
#    - If score < threshold AND iterations < 6:
#      → Go to REFINEMENT
#
# 5. REFINEMENT PHASE (if needed)
#    - Sends report + critic feedback to Claude
#    - Claude improves specific weak areas
#    - Preserves strong sections
#    - Returns enhanced report
#    - Goes back to CRITIQUE for re-evaluation
#
# 6. OUTPUT
#    - Saves to reports/ directory as Markdown
#    - Optionally exports JSON metadata
#    - Returns scores, history, final report


# ============================================================================
# UNDERSTANDING QUALITY SCORES
# ============================================================================

# The system evaluates each report on 5 dimensions:
#
# Factual Accuracy (0-10)
#   10 = All claims verifiable, well-sourced, current
#    7 = Most claims accurate, mostly well-sourced
#    4 = Mixed accuracy, some unsourced claims
#    1 = Many inaccuracies, poor sourcing
#
# Completeness (0-10)
#   10 = Covers all important angles thoroughly
#    7 = Covers main points, some aspects brief
#    4 = Misses several important perspectives
#    1 = Major gaps in coverage
#
# Clarity & Readability (0-10)
#   10 = Excellent writing, engaging, highly readable
#    7 = Good writing, mostly clear, slight repetition
#    4 = Adequate writing, some unclear passages
#    1 = Confusing, poorly written
#
# Structure (0-10)
#   10 = Logical flow, perfect organization, smooth transitions
#    7 = Good structure, mostly logical flow
#    4 = Adequate structure, some organization issues
#    1 = Poor organization, hard to follow
#
# Depth (0-10)
#   10 = Sophisticated analysis, nuanced insights
#    7 = Good depth, meaningful analysis
#    4 = Surface level with some depth
#    1 = Purely surface level
#
# FINAL SCORE = Average of 5 dimensions
# PASSING = Average ≥ 7.0 (default threshold)


# ============================================================================
# COMMON QUESTIONS
# ============================================================================

# Q: How long does report generation take?
# A: Typically 2-5 minutes depending on:
#    - Topic complexity
#    - Number of iterations needed
#    - API response times
#    - Internet speed

# Q: Can I use this without API keys?
# A: No, you need both:
#    - Anthropic API key (for Claude AI)
#    - Tavily API key (for web search)
#    Both are free to get started

# Q: How much does it cost?
# A: Pricing depends on usage:
#    - Anthropic: ~$0.003 per 1M input tokens, ~$0.015 per 1M output tokens
#    - Tavily: Free tier available, paid plans start $10/month
#    - Typical report: ~$0.05-0.10

# Q: Can I customize the report type?
# A: Yes! Choose from:
#    - academic: Rigorous, well-cited, formal
#    - business: Executive summary, data-driven, actionable
#    - technical: Detailed, precise, implementation-focused
#    - news-style: Engaging, journalistic, narrative

# Q: What if quality stays below threshold?
# A: The system tries up to 6 refinement iterations
#    If it still doesn't meet threshold:
#    - You get the best version generated
#    - Check the weaknesses list for why
#    - Try with lower threshold or simpler topic

# Q: How do I use the output?
# A: Reports are saved to reports/ directory as:
#    - Markdown (.md) - readable, shareable, can convert to PDF
#    - JSON metadata - programmatic access to scores/feedback
#    - Can import to Word, Google Docs, etc.

# Q: Can I batch generate multiple reports?
# A: Yes! Create a script like:
#    
#    topics = ["Topic 1", "Topic 2", "Topic 3"]
#    for topic in topics:
#        result = generate_report(topic=topic)
#        print(f"{topic}: {result['final_score']}/10")

# Q: What if a topic has no/limited information?
# A: The system will:
#    - Search for what it can find
#    - Generate best effort report
#    - Quality score may be lower
#    - Suggestions will flag data limitations


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Problem: "API Key not found" or "Invalid API key"
# Solution:
#   1. Check .env file exists in project root
#   2. Verify key format (starts with sk-ant- for Anthropic)
#   3. Make sure no extra spaces or quotes
#   4. Test key is active on provider's dashboard

# Problem: "No sources found" or "Web search failed"
# Solution:
#   1. Check internet connection
#   2. Try a broader search term
#   3. Wait a moment and retry (may be rate limited)
#   4. Check Tavily API status/quota

# Problem: "Report quality stuck below 7.0"
# Solution:
#   1. Lower the threshold (try 6.5 or 6.0)
#   2. Topic may have limited information available
#   3. Increase max_iterations (try 8-10)
#   4. Simplify or reword the topic

# Problem: Script hangs or times out
# Solution:
#   1. May be scraping slow websites
#   2. Reduce max_iterations to see partial results
#   3. Try a different topic
#   4. Check network connection

# Problem: Reports seem generic or shallow
# Solution:
#   1. Use more specific topic (e.g., not just "AI" but "AI in Legal Discovery")
#   2. Choose appropriate report type
#   3. Set higher quality threshold (forces more refinement)
#   4. Allow more iterations


# ============================================================================
# NEXT STEPS
# ============================================================================

# 1. Generate your first report:
#    python cli.py --topic "Your Topic Here" --verbose

# 2. Try the web UI:
#    streamlit run streamlit_app.py

# 3. Explore report types:
#    - Generate same topic with all 4 report types
#    - Compare the different structures and styles

# 4. Experiment with parameters:
#    - Try higher quality threshold (8.0-9.0)
#    - Watch how more iterations improve quality
#    - See which topics need more refinement

# 5. Build custom workflows:
#    - Create Python scripts for batch generation
#    - Integrate into your pipeline
#    - Export reports programmatically

# 6. Monitor costs:
#    - Track API usage in Anthropic/Tavily dashboards
#    - Adjust max_iterations based on cost vs quality tradeoff


# ============================================================================
# RESOURCES
# ============================================================================

# Documentation:
#   - Read: SYSTEM_README.md (comprehensive guide)
#   - Code: report_generator.py (main system)
#   - Web: streamlit_app.py (interactive UI)
#   - CLI: cli.py (command line)

# API Documentation:
#   - Anthropic: https://docs.anthropic.com/
#   - Tavily: https://docs.tavily.com/
#   - LangGraph: https://python.langchain.com/docs/langgraph/

# Getting Help:
#   - Check SYSTEM_README.md troubleshooting section
#   - Review API error messages
#   - Check .env configuration
#   - Verify API keys are active


print("""
✨ You're all set! Ready to generate amazing reports.

Next: 
  1. Set your API keys in .env
  2. Try: python cli.py --topic "Your Topic" --verbose
  3. Or: streamlit run streamlit_app.py

Happy reporting! 🚀
""")
