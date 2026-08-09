from typing import Any

from .state import AgentState


def verify_hypotheses(
    hypotheses: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Verify hypotheses against the observations collected
    during the investigation.
    """

    verified = []

    observation_text = str(observations).lower()

    for hypothesis in hypotheses:
        cause = hypothesis.get("cause", "").lower()

        supporting_evidence = []

        if "database connection pool exhaustion" in cause:
            if "pool exhausted" in observation_text:
                supporting_evidence.append(
                    "Logs contain pool exhaustion evidence."
                )

            if "db write timeout" in observation_text:
                supporting_evidence.append(
                    "Logs contain repeated DB write timeout errors."
                )

        elif "connection-pool configuration change" in cause:
            if "connection pool size" in observation_text:
                supporting_evidence.append(
                    "Recent deployment changed connection pool configuration."
                )

        elif "retry amplification" in cause:
            if "retry wrapper" in observation_text:
                supporting_evidence.append(
                    "Recent deployment introduced a retry wrapper."
                )

        verified.append(
            {
                **hypothesis,
                "verified": len(supporting_evidence) > 0,
                "supporting_evidence": supporting_evidence,
            }
        )

    return verified


def verifier_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible verifier node.
    """

    hypotheses = state.get("hypotheses", [])
    observations = state.get("observations", [])

    verified_hypotheses = verify_hypotheses(
        hypotheses,
        observations,
    )

    evidence = []

    for hypothesis in verified_hypotheses:
        if hypothesis["verified"]:
            evidence.append(
                {
                    "hypothesis": hypothesis["cause"],
                    "confidence": hypothesis["confidence"],
                    "supporting_evidence": hypothesis[
                        "supporting_evidence"
                    ],
                }
            )

    return {
        "hypotheses": verified_hypotheses,
        "evidence": evidence,
    }