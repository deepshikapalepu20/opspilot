from pydantic import BaseModel, Field
from typing import Literal, Optional


class QueryMetricsArgs(BaseModel):
    service: str = Field(..., description="Service name, e.g. 'checkout-api'")
    metric: Literal["latency_ms_p95", "error_rate_pct"] = Field(...)
    start: str = Field(..., description="ISO8601 start time")
    end: str = Field(..., description="ISO8601 end time")


class SearchLogsArgs(BaseModel):
    service: str
    level: Optional[Literal["INFO", "WARN", "ERROR"]] = None
    keyword: Optional[str] = Field(
        None,
        description="Substring to search for in log messages"
    )
    start: str
    end: str


class GetDeploymentsArgs(BaseModel):
    service: str
    since: str = Field(
        ...,
        description="ISO8601 — only deployments after this time"
    )


class SearchIncidentsArgs(BaseModel):
    service: Optional[str] = None
    keyword: str = Field(
        ...,
        description="Free-text search over title/root_cause"
    )


class RetrieveRunbookArgs(BaseModel):
    query: str = Field(
        ...,
        description="Natural-language question to search the runbook/knowledge base"
    )
    service: Optional[str] = None


class CreateIncidentReportArgs(BaseModel):
    incident_title: str
    likely_root_cause: str
    confidence_pct: int = Field(..., ge=0, le=100)
    evidence: list[str]
    recommended_action: str
    requires_approval: bool


class RequestRollbackArgs(BaseModel):
    service: str
    deployment_id: str
    reason: str


# Registry of {tool_name: pydantic schema}, used by registry.py to validate
# arguments AND to auto-generate the OpenAI-style tool-use JSON schema.

TOOL_SCHEMAS = {
    "query_metrics": QueryMetricsArgs,
    "search_logs": SearchLogsArgs,
    "get_deployments": GetDeploymentsArgs,
    "search_incidents": SearchIncidentsArgs,
    "retrieve_runbook": RetrieveRunbookArgs,
    "create_incident_report": CreateIncidentReportArgs,
    "request_rollback": RequestRollbackArgs,
}