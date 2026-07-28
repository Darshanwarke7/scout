from pydantic import BaseModel
from typing import Optional


class ResearchRequest(BaseModel):
    query: str


class SessionSummary(BaseModel):
    id: int
    query: str
    created_at: str
    final_report: Optional[str] = None


class SessionDetail(SessionSummary):
    trace: list
