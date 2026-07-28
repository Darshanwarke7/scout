import json
import os
import shutil
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend import db
from backend.agent import run_research
from backend.rag.store import store
from backend.rag.ingest import extract_text
from backend.schemas import ResearchRequest

db.init_db()

app = FastAPI(title="Scout — AI Research Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")


@app.post("/api/research")
def research(req: ResearchRequest):
    """Streams the agent's trace as Server-Sent Events, then a final event."""
    session_id = db.create_session(req.query)

    def event_stream():
        yield _sse({"type": "session", "id": session_id})
        final_text = ""
        for event in run_research(req.query):
            db.append_trace_step(session_id, event)
            if event["type"] == "final":
                final_text = event["text"]
            yield _sse(event)
        db.finalize_session(session_id, final_text)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".txt", ".md"):
        raise HTTPException(400, "Only .pdf, .txt, and .md files are supported.")

    dest_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    text = extract_text(dest_path)
    chunk_count = store.add_document(text, source=file.filename)
    return {"filename": file.filename, "chunks_indexed": chunk_count}


@app.get("/api/knowledge-base")
def knowledge_base_stats():
    return store.stats()


@app.get("/api/history")
def history():
    return db.list_sessions()


@app.get("/api/history/{session_id}")
def history_detail(session_id: int):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    return session


# Serve the frontend as static files (mounted last so /api routes win).
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
