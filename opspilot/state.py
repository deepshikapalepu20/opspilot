from typing import Any, TypedDict


class AgentState(TypedDict, total=False):

    # ========================================================
    # INVESTIGATION INPUT
    # ========================================================

    goal: str

    # ========================================================
    # PLANNING
    # ========================================================

    plan: list[str]

    # ========================================================
    # TOOL OBSERVATIONS
    # ========================================================

    observations: list[dict[str, Any]]

    tool_calls: list[dict[str, Any]]

    # ========================================================
    # HYPOTHESIS
    # ========================================================

    hypotheses: list[dict[str, Any]]

    evidence: list[dict[str, Any]]

    selected_hypothesis: str | None

    # ========================================================
    # AGENT ITERATION
    # ========================================================

    iteration: int

    max_iterations: int

    terminated: bool

    termination_reason: str | None

    # ========================================================
    # REASONING / REFLECTION
    # ========================================================

    reflection: dict[str, Any] | None

    reflection_notes: list[str]

    # ========================================================
    # CONTROLLER GROUNDING
    # ========================================================

    controller_grounded: bool

    controller_grounded_hypothesis: str | None

    goal_evidence_status: str

    # ========================================================
    # CURRENT TOOL EXECUTION
    # ========================================================

    current_tool: str | None

    current_tool_arguments: dict[str, Any] | None

    last_tool_result: Any

    # ========================================================
    # HUMAN APPROVAL
    # ========================================================

    pending_approval: dict[str, Any] | None

    # ========================================================
    # ACTION EXECUTION
    # ========================================================

    action_execution: dict[str, Any] | None

    # ========================================================
    # POST-ACTION VERIFICATION
    # ========================================================

    verification_result: dict[str, Any] | None

    # ========================================================
    # INCIDENT STATUS
    # ========================================================

    incident_status: str

    # ========================================================
    # FINAL REPORT
    # ========================================================

    final_report: dict[str, Any] | None