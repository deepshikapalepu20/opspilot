from typing import Any

from .state import AgentState


def generate_hypotheses(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate candidate root causes from collected observations.
    """

    hypotheses = []

    combined_text = str(observations).lower()

    # Database timeout evidence
    if "db write timeout" in combined_text or "pool exhausted" in combined_text:
        hypotheses.append(
            {
                "cause": "Database connection pool exhaustion",
                "confidence": 85,
                "reason": (
                    "ERROR logs show repeated DB write timeouts "
                    "and pool exhaustion."
                ),
            }
        )

    # Deployment evidence
    if "connection pool size" in combined_text:
        hypotheses.append(
            {
                "cause": "Recent connection-pool configuration change",
                "confidence": 80,
                "reason": (
                    "The latest deployment changed the database "
                    "connection pool configuration."
                ),
            }
        )

    # Retry-related evidence
    if "retry wrapper" in combined_text:
        hypotheses.append(
            {
                "cause": "Retry amplification",
                "confidence": 65,
                "reason": (
                    "The latest deployment introduced a retry wrapper "
                    "around database writes."
                ),
            }
        )

    if not hypotheses:
        hypotheses.append(
            {
                "cause": "Unknown",
                "confidence": 0,
                "reason": "Insufficient evidence to determine a root cause.",
            }
        )

    hypotheses.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    return hypotheses


def hypothesis_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible hypothesis generation node.
    """

    observations = state.get("observations", [])

    hypotheses = generate_hypotheses(observations)

    return {
        "hypotheses": hypotheses,
    }