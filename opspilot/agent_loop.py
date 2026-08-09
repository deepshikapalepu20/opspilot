from typing import Any
from .report import report_node
from .planner import planner_node
from .hypothesis import hypothesis_node
from .verifier import verifier_node
from .reflection import reflection_node
from .approval import approval_node
from .state import AgentState
from .tools import (
    query_metrics,
    search_logs,
    get_deployments,
    search_incidents,
    retrieve_runbook,
)

def run_investigation(goal: str) -> dict[str, Any]:
    """
    Run the OpsPilot investigation pipeline.

    Flow:
        Planner
          ↓
        Hypothesis
          ↓
        Verifier
          ↓
        Reflection
          ↓
        Approval
    """

    # Initial agent state
    state: AgentState = {
        "goal": goal,
        "plan": [],
        "observations": [],
        "tool_calls": [],
        "hypotheses": [],
        "evidence": [],
        "iteration": 0,
        "max_iterations": 12,
        "pending_approval": None,
        "final_report": None,
    }

    # -------------------------------------------------
    # 1. PLAN
    # -------------------------------------------------

    plan_result = planner_node(state)
    state.update(plan_result)

    print("\n=== PLAN ===")
    for step in state.get("plan", []):
        print(f"- {step}")

    # -------------------------------------------------
    # 2. COLLECT REAL OBSERVATIONS USING TOOLS
    # -------------------------------------------------

    service = "checkout-api"
    start = "2026-08-03T14:00:00Z"
    end = "2026-08-03T14:20:00Z"

    observations = []
    tool_calls = []

    # Metrics
    metrics = query_metrics(
        service,
        "latency_ms_p95",
        start,
        end,
    )

    observations.append({
        "source": "metrics",
        "data": metrics,
    })

    tool_calls.append({
        "tool": "query_metrics",
        "result": metrics,
    })

    # Error logs
    logs = search_logs(
        service,
        start,
        end,
        level="ERROR",
    )

    observations.append({
        "source": "logs",
        "data": logs,
    })

    tool_calls.append({
        "tool": "search_logs",
        "result": logs,
    })

    # Recent deployments
    deployments = get_deployments(
        service,
        "2026-08-01T00:00:00Z",
    )

    observations.append({
        "source": "deployments",
        "data": deployments,
    })

    tool_calls.append({
        "tool": "get_deployments",
        "result": deployments,
    })

    # Previous incidents
    incidents = search_incidents(
        service=service,
        keyword="latency",
    )

    observations.append({
        "source": "incidents",
        "data": incidents,
    })

    tool_calls.append({
        "tool": "search_incidents",
        "result": incidents,
    })

    # Runbook
    runbook = retrieve_runbook(
        "database connection pool exhaustion",
        service=service,
    )

    observations.append({
        "source": "runbook",
        "data": runbook,
    })

    tool_calls.append({
        "tool": "retrieve_runbook",
        "result": runbook,
    })

    state["observations"] = observations
    state["tool_calls"] = tool_calls

    print("\n=== TOOL OBSERVATIONS ===")

    for observation in observations:
        print(f"\n[{observation['source']}]")
        print(observation["data"])

    hypothesis_result = hypothesis_node(state)
    state.update(hypothesis_result)

    print("\n=== HYPOTHESES ===")
    for hypothesis in state.get("hypotheses", []):
        print(hypothesis)

    # -------------------------------------------------
    # 3. VERIFY
    # -------------------------------------------------

    verifier_result = verifier_node(state)
    state.update(verifier_result)

    print("\n=== VERIFICATION ===")
    for hypothesis in state.get("hypotheses", []):
        print(hypothesis)

    print("\n=== EVIDENCE ===")
    for item in state.get("evidence", []):
        print(item)

    # -------------------------------------------------
    # 4. REFLECTION
    # -------------------------------------------------

    reflection_result = reflection_node(state)
    state.update(reflection_result)

    print("\n=== REFLECTION ===")
    print(state.get("reflection"))

    # -------------------------------------------------
    # 5. APPROVAL
    # -------------------------------------------------

    reflection = state.get("reflection", {})

    if not reflection.get("continue_investigation", True):
        approval_result = approval_node(state)
        state.update(approval_result)

        print("\n=== APPROVAL ===")
        print(state.get("pending_approval"))

        report_result = report_node(state)
        state.update(report_result)

        print("\n=== FINAL REPORT ===")
        print(state.get("final_report"))

    return state