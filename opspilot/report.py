from typing import Any

from .llm import generate_response


def create_incident_report(state: dict[str, Any]) -> dict[str, Any]:
    """
    Create the final structured incident report from the investigation state.
    """

    hypotheses = state.get("hypotheses", [])
    evidence = state.get("evidence", [])
    reflection = state.get("reflection", {})
    approval = state.get("pending_approval")

    selected = reflection.get("selected_hypothesis", {})

    incident_title = state.get(
        "goal",
        "Unknown incident"
    )

    likely_root_cause = selected.get(
        "cause",
        "Unknown root cause"
    )

    confidence_pct = selected.get(
        "confidence",
        0
    )

    evidence_summary = []

    for item in evidence:
        evidence_summary.append(
            f"{item.get('hypothesis')}: "
            f"{', '.join(item.get('supporting_evidence', []))}"
        )

    recommended_action = (
        approval.get("action")
        if approval
        else "No high-impact action recommended"
    )

    requires_approval = bool(
        approval and approval.get("status") == "pending"
    )

    # Prepare structured investigation information for the LLM.
    investigation_context = {
        "incident": incident_title,
        "root_cause": likely_root_cause,
        "confidence": confidence_pct,
        "evidence": evidence_summary,
        "recommended_action": recommended_action,
    }

    prompt = f"""
You are an SRE incident investigation assistant.

Analyze the following investigation results.

Investigation:
{investigation_context}

Provide a concise incident analysis containing:

1. Root cause
2. Evidence
3. Impact
4. Recommended action

Do not invent facts that are not present in the investigation.
Base the explanation only on the supplied evidence.
"""

    try:
        llm_analysis = generate_response(prompt)
    except Exception as exc:
        llm_analysis = (
            f"LLM analysis unavailable: {exc}"
        )

    return {
        "incident_title": incident_title,
        "likely_root_cause": likely_root_cause,
        "confidence_pct": confidence_pct,
        "evidence": evidence_summary,
        "recommended_action": recommended_action,
        "requires_approval": requires_approval,
        "llm_analysis": llm_analysis,
    }


def report_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate and store the final incident report.
    """

    report = create_incident_report(state)

    return {
        "final_report": report
    }