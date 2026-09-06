from typing import Any

from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .planner import planner_node
from .hypothesis import hypothesis_node
from .verifier import verifier_node
from .reflection import reflection_node
from .approval import approval_node
from .report import report_node


# ============================================================
# LANGGRAPH NODE: INITIAL PLANNER
# ============================================================

def lg_planner(
    state: AgentState,
) -> dict[str, Any]:
    """
    Initial deterministic investigation planning node.

    Reuses the existing planner implementation.
    """

    print("\n=== LANGGRAPH: PLANNER ===")

    return planner_node(state)


# ============================================================
# LANGGRAPH NODE: INVESTIGATION
# ============================================================

def lg_investigation(
    state: AgentState,
) -> dict[str, Any]:
    """
    Execute the existing mature OpsPilot investigation
    controller.

    The controller in agent_loop.py remains responsible for:

    - Groq/Qwen tool decisions
    - tool argument normalization
    - duplicate-call protection
    - fallback evidence gathering
    - hard-evidence detection
    - controller grounding
    - investigation termination
    """

    from .agent_loop import _run_dynamic_tool_loop

    goal = state.get(
        "goal",
        "",
    )

    print(
        "\n=== LANGGRAPH: INVESTIGATION ==="
    )

    updated_state = _run_dynamic_tool_loop(
        goal,
        state,
    )

    return updated_state


# ============================================================
# LANGGRAPH NODE: CONTROLLER GROUNDING
# ============================================================

def lg_controller_grounding(
    state: AgentState,
) -> dict[str, Any]:
    """
    Apply the deterministic controller grounding layer.

    This preserves authoritative operational evidence such as:

        DB write timeout after 3 retries (pool exhausted)

    without asking the LLM to reinterpret already-observed
    hard evidence.
    """

    from .agent_loop import _apply_controller_grounding

    print(
        "\n=== LANGGRAPH: CONTROLLER GROUNDING ==="
    )

    grounded = _apply_controller_grounding(
        state
    )

    return {
        "controller_grounded": grounded,
    }


# ============================================================
# LANGGRAPH NODE: HYPOTHESIS
# ============================================================

def lg_hypothesis(
    state: AgentState,
) -> dict[str, Any]:
    """
    Generate root-cause hypotheses from collected evidence.
    """

    print(
        "\n=== LANGGRAPH: HYPOTHESIS ==="
    )

    return hypothesis_node(state)


# ============================================================
# LANGGRAPH NODE: VERIFIER
# ============================================================

def lg_verifier(
    state: AgentState,
) -> dict[str, Any]:
    """
    Verify generated hypotheses against collected evidence.
    """

    print(
        "\n=== LANGGRAPH: VERIFIER ==="
    )

    return verifier_node(state)


# ============================================================
# LANGGRAPH NODE: REFLECTION
# ============================================================

def lg_reflection(
    state: AgentState,
) -> dict[str, Any]:
    """
    Critique the investigation and identify evidence gaps.
    """

    print(
        "\n=== LANGGRAPH: REFLECTION ==="
    )

    return reflection_node(state)


# ============================================================
# LANGGRAPH NODE: EVIDENCE GATE
# ============================================================

def lg_evidence_gate(
    state: AgentState,
) -> dict[str, Any]:
    """
    Apply the existing programmatic evidence gate.

    The evidence gate is deterministic and therefore does not
    rely on the LLM to decide whether the investigation has
    sufficient operational evidence.
    """

    from .agent_loop import _evidence_gate

    print(
        "\n=== LANGGRAPH: EVIDENCE GATE ==="
    )

    passed, reason = _evidence_gate(
        state
    )

    print(
        "Passed:",
        passed,
    )

    print(
        "Reason:",
        reason,
    )

    if passed:
        return {
            "incident_status": "completed",
            "termination_reason": "reported",
        }

    return {
        "incident_status": "inconclusive",
        "termination_reason": "insufficient_evidence",
    }


# ============================================================
# LANGGRAPH NODE: APPROVAL
# ============================================================

def lg_approval(
    state: AgentState,
) -> dict[str, Any]:
    """
    Create a human approval request when required.

    The approval request itself remains pending and does not
    execute any high-impact action.

    The investigation workflow is considered complete once
    the approval request has been created.
    """

    print(
        "\n=== LANGGRAPH: APPROVAL ==="
    )

    approval_result = approval_node(
        state
    )

    return {
        **approval_result,
        "incident_status": "completed",
    }


# ============================================================
# LANGGRAPH NODE: REPORT
# ============================================================

def lg_report(
    state: AgentState,
) -> dict[str, Any]:
    """
    Generate the final investigation report.

    When the deterministic controller has already established
    authoritative evidence, use the controller-grounded report
    builder instead of asking the LLM to reinterpret the evidence.
    """

    from .agent_loop import (
        _apply_controller_grounding,
        _build_controller_grounded_report,
    )

    print(
        "\n=== LANGGRAPH: REPORT ==="
    )

    if _apply_controller_grounding(
        state
    ):
        return _build_controller_grounded_report(
            state
        )

    return report_node(
        state
    )


# ============================================================
# ROUTING HELPER: ROLLBACK GOAL
# ============================================================

def _goal_requires_rollback(
    state: AgentState,
) -> bool:
    """
    Determine whether the investigation goal explicitly
    asks about rollback or reverting a deployment.

    This function only affects graph routing.

    It does NOT execute a rollback.
    """

    goal = state.get(
        "goal",
        "",
    )

    goal = goal.lower()

    rollback_terms = (
        "rollback",
        "roll back",
        "rolled back",
        "roll-back",
        "revert deployment",
        "revert the deployment",
        "revert latest deployment",
        "revert the latest deployment",
    )

    return any(
        term in goal
        for term in rollback_terms
    )


# ============================================================
# ROUTING: AFTER PLANNER
# ============================================================

def route_after_planner(
    state: AgentState,
) -> str:
    """
    Initial planning always proceeds to the investigation
    controller.
    """

    return "investigation"


# ============================================================
# ROUTING: AFTER INVESTIGATION
# ============================================================

def route_after_investigation(
    state: AgentState,
) -> str:
    """
    Decide whether the investigation has reached a
    controller-grounded conclusion or needs normal
    LLM reasoning.

    Rollback-related goals are allowed to enter the
    approval path after evidence has been gathered.
    """

    if state.get(
        "pending_approval"
    ):
        return "approval"

    if _goal_requires_rollback(
        state
    ):
        return "approval"

    if state.get(
        "controller_grounded",
        False,
    ):
        return "evidence_gate"

    if state.get(
        "terminated",
        False,
    ):
        return "evidence_gate"

    return "hypothesis"


# ============================================================
# ROUTING: AFTER GROUNDING
# ============================================================

def route_after_grounding(
    state: AgentState,
) -> str:
    """
    Controller-grounded investigations normally proceed
    directly to the evidence gate.

    Exception:

    If the goal explicitly concerns rollback, route through
    the approval node first.

    This creates:

        investigation
            ↓
        controller grounding
            ↓
        approval
            ↓
        report

    No rollback is executed automatically.
    """

    if _goal_requires_rollback(
        state
    ):
        return "approval"

    if state.get(
        "controller_grounded",
        False,
    ):
        return "evidence_gate"

    return "hypothesis"


# ============================================================
# ROUTING: AFTER VERIFIER
# ============================================================

def route_after_verifier(
    state: AgentState,
) -> str:
    """
    Move from verification to reflection.
    """

    return "reflection"


# ============================================================
# ROUTING: AFTER REFLECTION
# ============================================================

def route_after_reflection(
    state: AgentState,
) -> str:
    """
    Decide whether reflection requires another investigation
    cycle or whether the evidence should be gated.
    """

    reflection = state.get(
        "reflection"
    )

    if isinstance(
        reflection,
        dict,
    ):

        if reflection.get(
            "needs_replan",
            False,
        ):
            return "investigation"

    return "evidence_gate"


# ============================================================
# ROUTING: AFTER EVIDENCE GATE
# ============================================================

def route_after_evidence_gate(
    state: AgentState,
) -> str:
    """
    Route according to the result of the evidence gate.

    Pending approval takes precedence.
    Otherwise proceed to the final report.
    """

    if state.get(
        "pending_approval"
    ):
        return "approval"

    return "report"


# ============================================================
# ROUTING: AFTER APPROVAL
# ============================================================

def route_after_approval(
    state: AgentState,
) -> str:
    """
    Approval requests terminate the investigation graph
    through the report path.

    The approval node only creates a pending request.
    It does not execute the rollback.
    """

    return "report"


# ============================================================
# BUILD LANGGRAPH
# ============================================================

def build_graph():
    """
    Build and compile the OpsPilot LangGraph workflow.

    IMPORTANT:

    Node names intentionally do NOT match AgentState keys.

    For example:

        Node: reflection_node
        State key: reflection

    This avoids LangGraph's state-key/node-name collision.
    """

    graph = StateGraph(
        AgentState
    )

    # --------------------------------------------------------
    # REGISTER NODES
    # --------------------------------------------------------

    graph.add_node(
        "planner_node",
        lg_planner,
    )

    graph.add_node(
        "investigation_node",
        lg_investigation,
    )

    graph.add_node(
        "controller_grounding_node",
        lg_controller_grounding,
    )

    graph.add_node(
        "hypothesis_node",
        lg_hypothesis,
    )

    graph.add_node(
        "verifier_node",
        lg_verifier,
    )

    graph.add_node(
        "reflection_node",
        lg_reflection,
    )

    graph.add_node(
        "evidence_gate_node",
        lg_evidence_gate,
    )

    graph.add_node(
        "approval_node",
        lg_approval,
    )

    graph.add_node(
        "report_node",
        lg_report,
    )

    # --------------------------------------------------------
    # START → PLANNER
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "planner_node",
    )

    # --------------------------------------------------------
    # PLANNER → INVESTIGATION
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "investigation": "investigation_node",
        },
    )

    # --------------------------------------------------------
    # INVESTIGATION → CONTROLLER GROUNDING
    # --------------------------------------------------------

    graph.add_edge(
        "investigation_node",
        "controller_grounding_node",
    )

    # --------------------------------------------------------
    # GROUNDING → NEXT REASONING STAGE
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "controller_grounding_node",
        route_after_grounding,
        {
            "evidence_gate": "evidence_gate_node",
            "hypothesis": "hypothesis_node",
            "approval": "approval_node",
        },
    )

    # --------------------------------------------------------
    # HYPOTHESIS → VERIFIER
    # --------------------------------------------------------

    graph.add_edge(
        "hypothesis_node",
        "verifier_node",
    )

    # --------------------------------------------------------
    # VERIFIER → REFLECTION
    # --------------------------------------------------------

    graph.add_edge(
        "verifier_node",
        "reflection_node",
    )

    # --------------------------------------------------------
    # REFLECTION → INVESTIGATION / EVIDENCE GATE
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "reflection_node",
        route_after_reflection,
        {
            "investigation": "investigation_node",
            "evidence_gate": "evidence_gate_node",
        },
    )

    # --------------------------------------------------------
    # EVIDENCE GATE → APPROVAL / REPORT
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "evidence_gate_node",
        route_after_evidence_gate,
        {
            "approval": "approval_node",
            "report": "report_node",
        },
    )

    # --------------------------------------------------------
    # APPROVAL → REPORT
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "approval_node",
        route_after_approval,
        {
            "report": "report_node",
        },
    )

    # --------------------------------------------------------
    # REPORT → END
    # --------------------------------------------------------

    graph.add_edge(
        "report_node",
        END,
    )

    return graph.compile()


# ============================================================
# PUBLIC LANGGRAPH RUNNER
# ============================================================

def run_langgraph_investigation(
    goal: str,
) -> AgentState:
    """
    Run an OpsPilot investigation through LangGraph.

    The original manual agent remains available through
    agent_loop.py and cli.py as the baseline implementation.
    """

    initial_state: AgentState = {
        "goal": goal,

        # ----------------------------------------------------
        # Planning
        # ----------------------------------------------------

        "plan": [],

        # ----------------------------------------------------
        # Evidence
        # ----------------------------------------------------

        "observations": [],
        "tool_calls": [],
        "hypotheses": [],
        "evidence": [],

        # ----------------------------------------------------
        # Reasoning
        # ----------------------------------------------------

        "reflection_notes": [],
        "reflection": None,
        "selected_hypothesis": None,

        # ----------------------------------------------------
        # Iteration
        # ----------------------------------------------------

        "iteration": 0,
        "max_iterations": 12,

        # ----------------------------------------------------
        # Termination
        # ----------------------------------------------------

        "terminated": False,
        "termination_reason": None,

        # ----------------------------------------------------
        # Controller grounding
        # ----------------------------------------------------

        "controller_grounded": False,
        "controller_grounded_hypothesis": None,
        "goal_evidence_status": "unknown",

        # ----------------------------------------------------
        # Tool execution
        # ----------------------------------------------------

        "current_tool": None,
        "current_tool_arguments": None,
        "last_tool_result": None,

        # ----------------------------------------------------
        # Approval
        # ----------------------------------------------------

        "pending_approval": None,

        # ----------------------------------------------------
        # Action execution
        # ----------------------------------------------------

        "action_execution": None,

        # ----------------------------------------------------
        # Verification
        # ----------------------------------------------------

        "verification_result": None,

        # ----------------------------------------------------
        # Incident
        # ----------------------------------------------------

        "incident_status": "investigating",

        # ----------------------------------------------------
        # Report
        # ----------------------------------------------------

        "final_report": None,
    }

    graph = build_graph()

    print(
        "\n========================================"
    )
    print(
        "       OPSPILOT LANGGRAPH START"
    )
    print(
        "========================================"
    )

    print(
        "\nGoal:",
        goal,
    )

    result = graph.invoke(
        initial_state
    )

    print(
        "\n========================================"
    )
    print(
        "      OPSPILOT LANGGRAPH COMPLETE"
    )
    print(
        "========================================"
    )

    print(
        "\nTermination:",
        result.get(
            "termination_reason"
        ),
    )

    print(
        "Incident status:",
        result.get(
            "incident_status"
        ),
    )

    print(
        "Iterations:",
        result.get(
            "iteration"
        ),
    )

    print(
        "Tools:",
        [
            call.get(
                "tool"
            )
            for call in result.get(
                "tool_calls",
                [],
            )
        ],
    )

    print(
        "Selected hypothesis:",
        result.get(
            "selected_hypothesis"
        ),
    )

    return result