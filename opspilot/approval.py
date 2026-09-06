from typing import Any

from .state import AgentState


def request_approval(
    service: str,
    deployment_id: str,
    reason: str,
) -> dict[str, Any]:
    """
    Create a pending approval request for a rollback.

    This function only creates an approval request.
    It does NOT execute the rollback.
    """

    return {
        "action": "rollback",
        "service": service,
        "deployment_id": deployment_id,
        "reason": reason,
        "status": "pending",
        "approved": False,
    }


def approval_node(
    state: AgentState,
) -> dict[str, Any]:
    """
    Create an approval request when the investigation
    recommends a rollback.

    Existing verified-hypothesis behavior is preserved.

    If no verified hypothesis exists, safely fall back to
    controller-grounded or selected hypothesis information.
    """

    hypothesis = state.get(
        "hypotheses",
        [],
    )

    # --------------------------------------------------------
    # EXISTING VERIFIED-HYPOTHESIS PATH
    # --------------------------------------------------------

    verified = [
        h
        for h in hypothesis
        if h.get(
            "verified",
            False,
        )
    ]

    strongest_cause = None

    if verified:
        strongest = max(
            verified,
            key=lambda h: h.get(
                "confidence",
                0,
            ),
        )

        strongest_cause = strongest.get(
            "cause",
            "unknown cause",
        )

    # --------------------------------------------------------
    # CONTROLLER-GROUNDED FALLBACK
    # --------------------------------------------------------

    if not strongest_cause:
        strongest_cause = state.get(
            "controller_grounded_hypothesis"
        )

    # --------------------------------------------------------
    # SELECTED-HYPOTHESIS FALLBACK
    # --------------------------------------------------------

    if not strongest_cause:
        strongest_cause = state.get(
            "selected_hypothesis"
        )

    # --------------------------------------------------------
    # SAFETY: NO EVIDENCE = NO APPROVAL REQUEST
    # --------------------------------------------------------

    if not strongest_cause:
        return {
            "pending_approval": None
        }

    # --------------------------------------------------------
    # CURRENT CHECKOUT-API DEPLOYMENT
    # --------------------------------------------------------

    approval = request_approval(
        service="checkout-api",
        deployment_id="checkout-v2.4",
        reason=(
            "Rollback recommended because "
            "the investigation established: "
            f"{strongest_cause}"
        ),
    )

    return {
        "pending_approval": approval
    }