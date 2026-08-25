from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

MAX_ITERATIONS = 8
MAX_TOOL_RETRIES = 2


# ============================================================
# STOP INVESTIGATION
# ============================================================

class StopInvestigation(Exception):

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# ============================================================
# HARD ITERATION LIMIT
# ============================================================

def check_hard_limits(
    state: dict[str, Any],
) -> None:

    iteration = state.get(
        "iteration",
        0,
    )

    max_iterations = state.get(
        "max_iterations",
        MAX_ITERATIONS,
    )

    if iteration >= max_iterations:

        raise StopInvestigation(
            "max_iterations_reached"
        )


# ============================================================
# DUPLICATE TOOL CALL DETECTION
# ============================================================

def is_duplicate_call(
    state: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
) -> bool:

    for call in state.get(
        "tool_calls",
        [],
    ):

        previous_tool = call.get(
            "tool"
        )

        previous_args = call.get(
            "arguments",
            {},
        )

        if (
            previous_tool == tool_name
            and previous_args == args
        ):
            return True

    return False


# ============================================================
# DUPLICATE CALL GUARD
# ============================================================

def check_duplicate_call(
    state: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
    justified_retry: bool = False,
) -> None:

    if (
        is_duplicate_call(
            state,
            tool_name,
            args,
        )
        and not justified_retry
    ):

        raise StopInvestigation(
            f"duplicate_call_blocked:{tool_name}"
        )


# ============================================================
# RETRY BUDGET
# ============================================================

def check_retry_budget(
    retry_counts: dict[str, int],
    tool_name: str,
) -> None:

    count = retry_counts.get(
        tool_name,
        0,
    )

    if count >= MAX_TOOL_RETRIES:

        raise StopInvestigation(
            f"retry_budget_exhausted:{tool_name}"
        )


# ============================================================
# EMPTY OBSERVATION DETECTION
# ============================================================

def is_empty_observation(
    observation: dict[str, Any],
) -> bool:

    if not observation:
        return True

    for key in (
        "points",
        "entries",
        "deployments",
        "incidents",
        "chunks",
    ):

        if (
            key in observation
            and len(observation[key]) == 0
        ):
            return True

    return False