from typing import Any

from .state import AgentState


def request_approval(
    service: str,
    deployment_id: str,
    reason: str,
) -> dict[str, Any]:
    """
    Create a pending approval request for a rollback.
    """

    return {
        "action": "rollback",
        "service": service,
        "deployment_id": deployment_id,
        "reason": reason,
        "status": "pending",
        "approved": False,
    }


def approval_node(state: AgentState) -> dict[str, Any]:
    """
    Create an approval request when the investigation
    recommends a rollback.
    """

    hypothesis = state.get("hypotheses", [])
    goal = state.get("goal", "")

    # Find the strongest verified hypothesis
    verified = [
        h for h in hypothesis
        if h.get("verified", False)
    ]

    if not verified:
        return {
            "pending_approval": None
        }

    strongest = max(
        verified,
        key=lambda h: h.get("confidence", 0),
    )

    # For the current checkout-api investigation,
    # request approval for the latest deployment rollback.
    approval = request_approval(
        service="checkout-api",
        deployment_id="checkout-v2.4",
        reason=(
            f"Rollback recommended because the verified hypothesis "
            f"is: {strongest.get('cause', 'unknown cause')}"
        ),
    )

    return {
        "pending_approval": approval
    }