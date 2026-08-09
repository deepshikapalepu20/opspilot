from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from opspilot.agent_loop import run_investigation


app = FastAPI(
    title="OpsPilot API",
    description="Agentic AI API for incident investigation",
    version="1.0.0",
)


class InvestigationRequest(BaseModel):
    goal: str


@app.get("/")
def root():
    return {
        "message": "OpsPilot API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/investigate")
def investigate(request: InvestigationRequest) -> dict[str, Any]:
    """
    Run the complete OpsPilot incident investigation pipeline.
    """

    result = run_investigation(request.goal)

    return result