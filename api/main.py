from typing import Any
import re
from fastapi import FastAPI
from pydantic import BaseModel

from opspilot.agent_loop import (
    run_investigation,
    execute_approved_action,
)


app = FastAPI(
    title="OpsPilot API",
    description="Agentic AI API for incident investigation",
    version="1.0.0",
)


# ============================================================
# REQUEST MODELS
# ============================================================

class InvestigationRequest(BaseModel):
    goal: str


class ApprovalRequest(BaseModel):
    approved: bool


# ============================================================
# GOAL NORMALIZATION
# ============================================================

def normalize_investigation_goal(goal: str) -> str:
    """
    Normalize common natural-language service names into
    the canonical service identifiers used by OpsPilot.
    """
    return re.sub(
        r"\bcheckout\s+api\b",
        "checkout-api",
        goal,
        flags=re.IGNORECASE,
    )


# ============================================================
# TEMPORARY SERVER STATE
# ============================================================
#
# This stores the latest investigation while the demo is
# running.
#
# For a production system, this should be replaced with
# persistent/session-based storage such as Redis or a database.
#

CURRENT_STATE: dict[str, Any] | None = None


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "OpsPilot API is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# INVESTIGATION ENDPOINT
# ============================================================

@app.post("/investigate")
def investigate(
    request: InvestigationRequest
) -> dict[str, Any]:

    global CURRENT_STATE

    print("\n=== NEW INVESTIGATION ===")
    print("Goal:", request.goal)

    normalized_goal = normalize_investigation_goal(
        request.goal
    )

    print("Normalized goal:", normalized_goal)

    result = run_investigation(
        normalized_goal
    )

    # Save the investigation state so that the
    # approval endpoint can continue from here.
    CURRENT_STATE = result

    return result


# ============================================================
# HUMAN APPROVAL ENDPOINT
# ============================================================

@app.post("/approve")
def approve(
    request: ApprovalRequest
) -> dict[str, Any]:

    global CURRENT_STATE

    print("\n=== APPROVAL REQUEST ===")
    print("Approved:", request.approved)

    # --------------------------------------------------------
    # Check whether an investigation exists
    # --------------------------------------------------------

    if CURRENT_STATE is None:

        return {
            "approved": request.approved,
            "status": "error",
            "message": (
                "No investigation is currently waiting "
                "for approval."
            ),
        }

    # --------------------------------------------------------
    # REJECT ACTION
    # --------------------------------------------------------

    if not request.approved:

        CURRENT_STATE["incident_status"] = (
            "action_rejected"
        )

        CURRENT_STATE["action_execution"] = {
            "status": "rejected",
            "message": "Action rejected by operator."
        }

        return {
            "approved": False,
            "status": "rejected",
            "message": "Action rejected by operator.",
            "incident_status": (
                CURRENT_STATE["incident_status"]
            ),
            "action_execution": (
                CURRENT_STATE["action_execution"]
            ),
            "verification_result": (
                CURRENT_STATE.get(
                    "verification_result"
                )
            ),
        }

    # --------------------------------------------------------
    # APPROVE ACTION
    # --------------------------------------------------------

    CURRENT_STATE = execute_approved_action(
        CURRENT_STATE
    )

    return {
        "approved": True,
        "status": "approved",
        "message": "Action approved by operator.",

        "incident_status": (
            CURRENT_STATE.get(
                "incident_status"
            )
        ),

        "action_execution": (
            CURRENT_STATE.get(
                "action_execution"
            )
        ),

        "verification_result": (
            CURRENT_STATE.get(
                "verification_result"
            )
        ),

        "final_report": (
            CURRENT_STATE.get(
                "final_report"
            )
        ),
    }