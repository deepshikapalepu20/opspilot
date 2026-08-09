from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    goal: str
    plan: list[str]

    observations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]

    hypotheses: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    iteration: int
    max_iterations: int

    pending_approval: dict[str, Any] | None

    final_report: dict[str, Any] | None