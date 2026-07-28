"""Turns an uploaded file into plain text ready for chunking."""
import os
from pypdf import PdfReader


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext in (".txt", ".md"):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .txt, or .md")
