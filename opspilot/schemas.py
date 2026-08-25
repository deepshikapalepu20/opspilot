from pydantic import BaseModel, Field
from typing import Literal, Optional


class QueryMetricsArgs(BaseModel):

    service: str = Field(
        ...,
        description="Service name, e.g. checkout-api"
    )

    metric: Literal[
        "latency_ms_p95",
        "error_rate_pct"
    ] = Field(...)

    start: Optional[str] = Field(
        None,
        description=(
            "ISO8601 start time. "
            "If omitted, use the investigation time window."
        )
    )

    end: Optional[str] = Field(
        None,
        description=(
            "ISO8601 end time. "
            "If omitted, use the investigation time window."
        )
    )


class SearchLogsArgs(BaseModel):

    service: str

    level: Optional[
        Literal["INFO", "WARN", "ERROR"]
    ] = None

    keyword: Optional[str] = Field(
        None,
        description="Substring to search for in log messages"
    )

    start: Optional[str] = Field(
        None,
        description=(
            "ISO8601 start time. "
            "If omitted, use the investigation time window."
        )
    )

    end: Optional[str] = Field(
        None,
        description=(
            "ISO8601 end time. "
            "If omitted, use the investigation time window."
        )
    )


class GetDeploymentsArgs(BaseModel):

    service: str

    since: Optional[str] = Field(
        None,
        description=(
            "ISO8601 timestamp. "
            "If omitted, search recent deployments."
        )
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
        description=(
            "Natural-language question to search "
            "the runbook/knowledge base"
        )
    )

    service: Optional[str] = None


class CreateIncidentReportArgs(BaseModel):

    incident_title: str

    likely_root_cause: str

    confidence_pct: int = Field(
        ...,
        ge=0,
        le=100
    )

    evidence: list[str]

    recommended_action: str

    requires_approval: bool


class RequestRollbackArgs(BaseModel):

    service: str

    deployment_id: str

    reason: str


# ============================================================
# TOOL SCHEMA REGISTRY
# ============================================================

TOOL_SCHEMAS = {

    "query_metrics":
        QueryMetricsArgs,

    "search_logs":
        SearchLogsArgs,

    "get_deployments":
        GetDeploymentsArgs,

    "search_incidents":
        SearchIncidentsArgs,

    "retrieve_runbook":
        RetrieveRunbookArgs,

    "create_incident_report":
        CreateIncidentReportArgs,

    "request_rollback":
        RequestRollbackArgs,
}