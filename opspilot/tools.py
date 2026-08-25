import json
from pathlib import Path
from datetime import datetime


# ============================================================
# DATA DIRECTORY
# ============================================================

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ============================================================
# DEFAULT INVESTIGATION WINDOW
# ============================================================

DEFAULT_START = "2026-08-03T14:00:00Z"
DEFAULT_END = "2026-08-03T14:20:00Z"
DEFAULT_DEPLOYMENT_SINCE = "2026-08-01T00:00:00Z"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _load_json(filename: str):
    path = DATA_DIR / filename

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_time(value: str) -> datetime:
    """
    Safely parse an ISO8601 timestamp.

    Empty or invalid timestamps are rejected with a clear
    error instead of causing an unhandled server exception.
    """

    if not value or not value.strip():
        raise ValueError(
            "Timestamp cannot be empty."
        )

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError:
        raise ValueError(
            f"Invalid ISO8601 timestamp: {value}"
        )


# ============================================================
# METRICS TOOL
# ============================================================

def query_metrics(
    service: str,
    metric: str,
    start: str | None = None,
    end: str | None = None,
):

    data = _load_json("metrics.json")

    # Use project investigation window if the LLM
    # fails to provide valid dates.
    start = start or DEFAULT_START
    end = end or DEFAULT_END

    if service not in data:
        return {
            "service": service,
            "metric": metric,
            "points": [],
            "error": "Unknown service",
        }

    if metric not in data[service]:
        return {
            "service": service,
            "metric": metric,
            "points": [],
            "error": "Unknown metric",
        }

    try:
        start_dt = _parse_time(start)
        end_dt = _parse_time(end)

    except ValueError as e:
        return {
            "service": service,
            "metric": metric,
            "points": [],
            "error": str(e),
        }

    points = []

    for point in data[service][metric]:

        timestamp = _parse_time(point["t"])

        if start_dt <= timestamp <= end_dt:
            points.append(point)

    return {
        "service": service,
        "metric": metric,
        "start": start,
        "end": end,
        "points": points,
    }


# ============================================================
# LOG SEARCH TOOL
# ============================================================

def search_logs(
    service: str,
    start: str | None = None,
    end: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
):

    logs = _load_json("logs.json")

    # Safe defaults for the static investigation dataset.
    start = start or DEFAULT_START
    end = end or DEFAULT_END

    try:
        start_dt = _parse_time(start)
        end_dt = _parse_time(end)

    except ValueError as e:
        return {
            "service": service,
            "count": 0,
            "logs": [],
            "error": str(e),
        }

    results = []

    for log in logs:

        if log["service"] != service:
            continue

        timestamp = _parse_time(log["t"])

        if not (start_dt <= timestamp <= end_dt):
            continue

        if level and log["level"] != level:
            continue

        if (
            keyword
            and keyword.lower()
            not in log["message"].lower()
        ):
            continue

        results.append(log)

    return {
        "service": service,
        "count": len(results),
        "logs": results,
    }


# ============================================================
# DEPLOYMENT SEARCH TOOL
# ============================================================

def get_deployments(
    service: str,
    since: str | None = None,
):

    deployments = _load_json("deployments.json")

    # Prevent the LLM from sending an empty timestamp.
    since = since or DEFAULT_DEPLOYMENT_SINCE

    try:
        since_dt = _parse_time(since)

    except ValueError as e:
        return {
            "service": service,
            "count": 0,
            "deployments": [],
            "error": str(e),
        }

    results = []

    for deployment in deployments:

        if deployment["service"] != service:
            continue

        deployed_at = _parse_time(
            deployment["deployed_at"]
        )

        if deployed_at >= since_dt:
            results.append(deployment)

    return {
        "service": service,
        "count": len(results),
        "deployments": results,
    }


# ============================================================
# PREVIOUS INCIDENT SEARCH
# ============================================================

def search_incidents(
    keyword: str,
    service: str | None = None,
):

    incidents = _load_json("incidents.json")

    keyword_lower = keyword.lower()

    results = []

    for incident in incidents:

        if service and incident["service"] != service:
            continue

        searchable_text = (
            incident["title"]
            + " "
            + incident["root_cause"]
        ).lower()

        if keyword_lower in searchable_text:

            results.append(incident)

    return {
        "count": len(results),
        "incidents": results,
    }


# ============================================================
# RUNBOOK / RAG RETRIEVAL
# ============================================================

def retrieve_runbook(
    query: str,
    service: str | None = None,
):
    """
    Retrieve operational knowledge using the RAG system.

    RAG searches across runbooks, troubleshooting guides,
    architecture documents, and historical incidents.

    Retrieved knowledge is informational evidence only.
    It does not directly execute remediation actions.
    """

    try:

        from opspilot.rag.retriever import retrieve

        result = retrieve(
            query=query,
            service=service,
        )

    except Exception as exc:

        return {
            "query": query,
            "service": service,
            "count": 0,
            "chunks": [],
            "error": (
                f"RAG retrieval failed: {exc}"
            ),
        }

    return {
        "query": query,
        "service": service,
        "count": result.get(
            "count",
            0,
        ),
        "chunks": result.get(
            "chunks",
            [],
        ),
        "query_used": result.get(
            "query_used",
            query,
        ),
    }


# ============================================================
# INCIDENT REPORT CREATION
# ============================================================

def create_incident_report(
    incident_title: str,
    likely_root_cause: str,
    confidence_pct: int,
    evidence: list[str],
    recommended_action: str,
    requires_approval: bool,
):

    return {
        "incident_title": incident_title,
        "likely_root_cause": likely_root_cause,
        "confidence_pct": confidence_pct,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "requires_approval": requires_approval,
        "status": "report_created",
    }


# ============================================================
# REQUEST ROLLBACK
# ============================================================

def request_rollback(
    service: str,
    deployment_id: str,
    reason: str,
):

    return {
        "status": "approval_required",
        "action": "rollback",
        "service": service,
        "deployment_id": deployment_id,
        "reason": reason,
        "message": (
            "Rollback is a high-impact action and "
            "requires human approval before execution."
        ),
    }


# ============================================================
# EXECUTE ROLLBACK
# ============================================================

def execute_rollback(
    service: str,
    deployment_id: str,
):
    """
    Simulate execution of a deployment rollback.

    This project currently uses static JSON operational
    data, so this function does not modify a real
    deployment or cloud environment.
    """

    return {
        "status": "executed",
        "action": "rollback",
        "service": service,
        "deployment_id": deployment_id,
        "message": (
            f"Rollback of deployment "
            f"{deployment_id} for service "
            f"{service} executed successfully."
        ),
    }