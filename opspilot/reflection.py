from typing import Any

from .state import AgentState


def reflect(
    hypotheses: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Decide whether the current investigation has enough
    evidence to produce a final conclusion.
    """

    verified = [
        h for h in hypotheses
        if h.get("verified", False)
    ]

    if not verified:
        return {
            "continue_investigation": True,
            "reason": "No hypothesis has been verified yet.",
        }

    strongest = max(
        verified,
        key=lambda h: h.get("confidence", 0),
    )

    confidence = strongest.get("confidence", 0)

    if confidence >= 80 and evidence:
        return {
            "continue_investigation": False,
            "reason": "Sufficient evidence supports the leading hypothesis.",
            "selected_hypothesis": strongest,
        }

    return {
        "continue_investigation": True,
        "reason": "Additional evidence is required.",
        "selected_hypothesis": strongest,
    }


def reflection_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible reflection node.
    """

    hypotheses = state.get("hypotheses", [])
    evidence = state.get("evidence", [])

    result = reflect(hypotheses, evidence)

    return {
        "observations": state.get("observations", []),
        "hypotheses": hypotheses,
        "evidence": evidence,
        "reflection": result,
    }