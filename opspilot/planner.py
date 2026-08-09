from typing import Any

from .state import AgentState


def create_plan(goal: str) -> list[str]:
    """
    Create a deterministic investigation plan from the incident goal.
    """

    goal_lower = goal.lower()

    plan = []

    # Metrics are normally the first source of evidence.
    plan.append("Query relevant service metrics for the affected time window.")

    # Logs help identify the concrete failure.
    plan.append("Search service logs for WARN and ERROR messages.")

    # Recent deployments are important for regression analysis.
    plan.append("Check recent deployments for changes affecting the service.")

    # Historical incidents provide precedent.
    plan.append("Search previous incidents for similar symptoms and root causes.")

    # Runbooks provide the operational remediation procedure.
    plan.append("Retrieve the relevant service runbook for investigation and remediation guidance.")

    return plan


def planner_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible planner node.
    """

    goal = state.get("goal", "")

    plan = create_plan(goal)

    return {
        "plan": plan,
        "iteration": state.get("iteration", 0),
    }