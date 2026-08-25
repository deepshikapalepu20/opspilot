from typing import Any

from .state import AgentState
from .llm import call_local_json


# ============================================================
# INITIAL PLAN
# ============================================================

def create_plan(
    goal: str,
) -> list[str]:
    """
    Create the initial investigation plan from the
    incident goal.

    The initial plan remains deterministic so that the
    investigation always starts with the standard
    operational evidence sources.
    """

    goal_lower = goal.lower()

    plan = []

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    plan.append(
        "Query relevant service metrics for the affected time window."
    )

    # --------------------------------------------------------
    # Logs
    # --------------------------------------------------------

    plan.append(
        "Search service logs for WARN and ERROR messages."
    )

    # --------------------------------------------------------
    # Deployments
    # --------------------------------------------------------

    plan.append(
        "Check recent deployments for changes affecting the service."
    )

    # --------------------------------------------------------
    # Historical incidents
    # --------------------------------------------------------

    plan.append(
        "Search previous incidents for similar symptoms and root causes."
    )

    # --------------------------------------------------------
    # Runbook
    # --------------------------------------------------------

    plan.append(
        "Retrieve the relevant service runbook for investigation and remediation guidance."
    )

    return plan


# ============================================================
# INITIAL PLANNER NODE
# ============================================================

def planner_node(
    state: AgentState,
) -> dict[str, Any]:
    """
    LangGraph-compatible planner node.
    """

    goal = state.get(
        "goal",
        "",
    )

    plan = create_plan(
        goal
    )

    return {
        "plan": plan,
        "iteration": state.get(
            "iteration",
            0,
        ),
    }


# ============================================================
# RE-PLANNING PROMPT
# ============================================================

REPLAN_PROMPT = """
You are the planning component of OpsPilot.

The incident investigation has already collected evidence,
generated hypotheses, verified them, and then performed a
reflection/critique.

The reflection determined that the investigation requires
additional evidence.

Your job is to create a revised investigation plan that
specifically addresses the identified evidence gap.

IMPORTANT RULES:

1. Use ONLY the information contained in the investigation
   context below.

2. Do not invent logs, metrics, deployments, incidents,
   configuration changes, or root causes.

3. Do not repeat investigation steps that have already
   produced sufficient evidence unless they are required
   to resolve a contradiction.

4. Focus the new plan on the evidence gap identified by
   reflection.

5. Prefer read-only investigative steps.

6. The plan should contain concrete operational investigation
   steps, not explanations.

7. Return ONLY valid JSON.

Required JSON format:

{{
    "plan": [
        "specific investigation step",
        "specific investigation step"
    ]
}}

INVESTIGATION GOAL:
{goal}

CURRENT PLAN:
{plan}

OBSERVATIONS:
{observations}

TOOL CALLS:
{tool_calls}

HYPOTHESES:
{hypotheses}

EVIDENCE:
{evidence}

VERIFICATION RESULT:
{verification_result}

REFLECTION:
{reflection}

REFLECTION REASON:
{reason}

SKIPPED STEPS:
{skipped_steps}
"""


# ============================================================
# BUILD RE-PLANNING CONTEXT
# ============================================================

def _build_replan_context(
    state: AgentState,
    reason: str,
) -> dict[str, Any]:
    """
    Build the investigation context used by the LLM
    during re-planning.
    """

    reflection = state.get(
        "reflection",
        {},
    )

    if not isinstance(
        reflection,
        dict,
    ):
        reflection = {}

    return {
        "goal": state.get(
            "goal",
            "",
        ),
        "plan": state.get(
            "plan",
            [],
        ),
        "observations": state.get(
            "observations",
            [],
        ),
        "tool_calls": state.get(
            "tool_calls",
            [],
        ),
        "hypotheses": state.get(
            "hypotheses",
            [],
        ),
        "evidence": state.get(
            "evidence",
            [],
        ),
        "verification_result": state.get(
            "verification_result",
            None,
        ),
        "reflection": reflection,
        "reason": reason,
        "skipped_steps": reflection.get(
            "skipped_steps",
            [],
        ),
    }


# ============================================================
# NORMALIZE RE-PLANNING RESULT
# ============================================================

def _normalize_replan_result(
    result: Any,
) -> list[str]:
    """
    Validate the plan returned by Qwen.

    If the model returns malformed data, raise an error
    rather than silently creating an invalid investigation.
    """

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Re-planner returned a non-object response."
        )

    plan = result.get(
        "plan",
        [],
    )

    if not isinstance(
        plan,
        list,
    ):
        raise ValueError(
            "Re-planner response does not contain a valid plan list."
        )

    normalized_plan = []

    for step in plan:

        if not isinstance(
            step,
            str,
        ):
            continue

        step = step.strip()

        if step:
            normalized_plan.append(
                step
            )

    if not normalized_plan:
        raise ValueError(
            "Re-planner returned an empty investigation plan."
        )

    return normalized_plan


# ============================================================
# RE-PLAN
# ============================================================

def replan(
    state: AgentState,
    reason: str,
) -> list[str]:
    """
    Generate a revised investigation plan after the
    reflection/critic identifies an evidence gap.

    This function is called by agent_loop.py when:

        reflection["needs_replan"] == True
    """

    context = _build_replan_context(
        state,
        reason,
    )

    prompt = REPLAN_PROMPT.format(
        goal=context["goal"],
        plan=context["plan"],
        observations=context["observations"],
        tool_calls=context["tool_calls"],
        hypotheses=context["hypotheses"],
        evidence=context["evidence"],
        verification_result=context[
            "verification_result"
        ],
        reflection=context[
            "reflection"
        ],
        reason=context[
            "reason"
        ],
        skipped_steps=context[
            "skipped_steps"
        ],
    )

    print(
        "\n=== RE-PLANNER ==="
    )

    print(
        "Generating revised investigation plan..."
    )

    try:

        result = call_local_json(
            prompt
        )

    except Exception as e:

        raise RuntimeError(
            "Re-planning failed while calling the "
            f"local LLM: {e}"
        ) from e

    new_plan = _normalize_replan_result(
        result
    )

    return new_plan