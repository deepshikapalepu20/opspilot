import json
from pathlib import Path
from datetime import datetime, timezone


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str):
    path = DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def query_metrics(
    service: str,
    metric: str,
    start: str,
    end: str,
):
    data = _load_json("metrics.json")

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

    start_dt = _parse_time(start)
    end_dt = _parse_time(end)

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


def search_logs(
    service: str,
    start: str,
    end: str,
    level: str | None = None,
    keyword: str | None = None,
):
    logs = _load_json("logs.json")

    start_dt = _parse_time(start)
    end_dt = _parse_time(end)

    results = []

    for log in logs:
        if log["service"] != service:
            continue

        timestamp = _parse_time(log["t"])

        if not (start_dt <= timestamp <= end_dt):
            continue

        if level and log["level"] != level:
            continue

        if keyword and keyword.lower() not in log["message"].lower():
            continue

        results.append(log)

    return {
        "service": service,
        "count": len(results),
        "logs": results,
    }


def get_deployments(
    service: str,
    since: str,
):
    deployments = _load_json("deployments.json")

    since_dt = _parse_time(since)

    results = []

    for deployment in deployments:
        if deployment["service"] != service:
            continue

        deployed_at = _parse_time(deployment["deployed_at"])

        if deployed_at >= since_dt:
            results.append(deployment)

    return {
        "service": service,
        "count": len(results),
        "deployments": results,
    }


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
            incident["title"] + " " +
            incident["root_cause"]
        ).lower()

        if keyword_lower in searchable_text:
            results.append(incident)

    return {
        "count": len(results),
        "incidents": results,
    }


def retrieve_runbook(
    query: str,
    service: str | None = None,
):
    runbooks_dir = DATA_DIR / "runbooks"

    if service:
        filename = f"{service}.md"
        path = runbooks_dir / filename

        if not path.exists():
            return {
                "service": service,
                "content": "",
                "error": "Runbook not found",
            }

        content = path.read_text(encoding="utf-8")

        return {
            "service": service,
            "query": query,
            "content": content,
        }

    results = []

    for path in runbooks_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")

        if query.lower() in content.lower():
            results.append({
                "file": path.name,
                "content": content,
            })

    return {
        "query": query,
        "results": results,
    }


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


def request_rollback(
    service: str,
    deployment_id: str,
    reason: str,
):
    return {
        "status": "approval_required",
        "service": service,
        "deployment_id": deployment_id,
        "reason": reason,
        "message": (
            "Rollback is a high-impact action and requires "
            "human approval before execution."
        ),
    }