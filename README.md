# Scout — an AI research agent you can watch think

Scout takes a research question, plans its own next step, calls tools
(web search, a local document knowledge base, a calculator), reads the
results, and repeats until it has enough to write a cited report. The
whole reasoning trace streams live to the browser instead of hiding
behind a spinner.

It's built to demonstrate the three things that actually separate an
"AI engineer" project from a wrapper around a chat API:

1. **An explicit agent loop** — no framework black box. `backend/agent.py`
   is ~120 lines you can read top to bottom: plan → tool call → observe → repeat.
2. **Retrieval over your own documents (RAG)** — local embeddings + FAISS,
   no hosted vector DB required.
3. **Observability** — every reasoning step, tool call, and tool result
   is a structured event, streamed over SSE and persisted to SQLite so
   past runs are inspectable, not thrown away.

## Architecture

```
frontend/          static HTML/CSS/JS — live trace UI + report + history
backend/
  main.py          FastAPI app: SSE research endpoint, uploads, history
  agent.py         the agent loop (plan -> tool_use -> observe -> repeat)
  tools/
    web_search.py       DuckDuckGo search (no API key needed)
    knowledge_base.py   retrieval over uploaded docs
    calculator.py       AST-restricted arithmetic (no eval())
  rag/
    store.py         FAISS index + sentence-transformers embeddings
    ingest.py         pdf/txt/md -> plain text
  db.py             SQLite: session history + full trace per session
data/               uploaded files + the persisted FAISS index
scout.db            created on first run
```

**Why these choices, for the "why did you build it this way" question in
an interview:**
- The agent loop is hand-rolled instead of using LangChain/LlamaIndex
  agents on purpose — it's the clearest way to *show* you understand
  what a tool-calling loop actually does, rather than importing it.
- Embeddings run locally (`sentence-transformers`) so the RAG half works
  with zero extra API keys or cost — swap in Voyage/OpenAI embeddings
  in `backend/rag/store.py` if you want higher retrieval quality later.
- Web search uses DuckDuckGo (`ddgs`, no key) for the same reason —
  swap in Tavily/Serper/Brave in `backend/tools/web_search.py` for
  production-quality results.
- History is SQLite, not because it needs to scale, but because a
  demo that can replay a past run is a lot more convincing than one
  that can't.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your GROQ_API_KEY (free at https://console.groq.com/keys)

uvicorn backend.main:app --reload
```

Open **http://localhost:8000**.

The first request will take a little longer than usual — it downloads
the `all-MiniLM-L6-v2` embedding model (~90MB) on first use.

## Using it

1. **Research tab** — type a question, hit run, watch the trace stream in.
2. **Knowledge base tab** — upload a `.pdf`, `.txt`, or `.md` file. Ask a
   question that touches it and watch the agent choose
   `search_knowledge_base` before reaching for the web.
3. **History tab** — every run is saved; click one to replay its full trace.

Good demo questions:
- "What's [some recent event] and how might it affect [some industry]?" — forces `web_search`
- Upload a resume or project doc, then ask "what's the strongest project in this document and why?" — forces `search_knowledge_base`
- "If a project grew from 950 to 1200 users, what's the percentage growth?" — forces `calculate`

## Deploying it

- **Backend**: any host that runs a long-lived Python process and
  supports streaming responses (Render, Railway, Fly.io). Set
  `GROQ_API_KEY` as an environment variable there.
- **Frontend**: already served by FastAPI (`StaticFiles`), so there's
  nothing extra to deploy — one service, one URL.

## Extending it

- Add a new tool: write a module in `backend/tools/` with a `SCHEMA` dict
  and a `run()` function, then register it in `TOOLS` / `TOOL_IMPL` in
  `backend/agent.py`.
- Swap the LLM: change `GROQ_MODEL` in `.env` (any Groq-hosted model that supports tool calling).
- Swap the search or embedding provider: see the "why these choices"
  note above — both are isolated behind a single function signature.

## Known limitations (worth saying out loud in an interview)

- Single-process vector store — fine for a demo, would move to a real
  vector DB (Qdrant/pgvector) for multi-user production use.
- No auth — this is a local/demo tool, not a multi-tenant app.
- The step limit (`MAX_AGENT_STEPS`) is a blunt guardrail against
  infinite tool-calling loops; a production version would add a
  token/cost budget too.
