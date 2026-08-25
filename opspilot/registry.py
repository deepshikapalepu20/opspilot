from typing import Any

from pydantic import ValidationError

from . import tools
from .schemas import TOOL_SCHEMAS


# ============================================================
# TOOL FUNCTION REGISTRY
# ============================================================
#
# Maps the tool name produced by the LLM to the actual
# Python function that performs the operation.
#
# Example:
#
# "search_logs"
#       ↓
# tools.search_logs
#
# ============================================================

TOOL_FUNCTIONS = {
    "query_metrics": tools.query_metrics,
    "search_logs": tools.search_logs,
    "get_deployments": tools.get_deployments,
    "search_incidents": tools.search_incidents,
    "retrieve_runbook": tools.retrieve_runbook,
    "create_incident_report": tools.create_incident_report,
    "request_rollback": tools.request_rollback,
}


# ============================================================
# HIGH-IMPACT TOOLS
# ============================================================
#
# These tools must not directly perform high-impact actions.
# They go through the approval layer.
#
# ============================================================

HIGH_IMPACT_TOOLS = {
    "request_rollback"
}


# ============================================================
# TOOL DISPATCH ERROR
# ============================================================

class ToolDispatchError(Exception):
    """
    Raised when a tool cannot be safely dispatched.
    """

    pass


# ============================================================
# GENERATE LLM TOOL DEFINITIONS
# ============================================================

def ollama_tool_definitions() -> list[dict[str, Any]]:
    """
    Generate OpenAI-style function-calling definitions
    from the Pydantic schemas.

    These definitions are sent to the local Ollama model
    so that the model knows which tools are available and
    what arguments each tool requires.
    """

    definitions = []

    for name, schema in TOOL_SCHEMAS.items():

        function = TOOL_FUNCTIONS.get(name)

        if function is None:

            raise ToolDispatchError(
                f"No Python function registered for tool '{name}'"
            )

        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,

                    "description": (
                        function.__doc__
                        or f"Call {name}"
                    ),

                    "parameters": (
                        schema.model_json_schema()
                    ),
                },
            }
        )

    return definitions


# ============================================================
# TOOL DISPATCH
# ============================================================

def dispatch(
    tool_name: str,
    raw_args: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate tool arguments using the corresponding
    Pydantic schema and then execute the registered
    Python function.
    """

    # --------------------------------------------------------
    # Check tool name
    # --------------------------------------------------------

    if tool_name not in TOOL_FUNCTIONS:

        raise ToolDispatchError(
            f"Unknown tool '{tool_name}'"
        )

    # --------------------------------------------------------
    # Check arguments
    # --------------------------------------------------------

    if not isinstance(raw_args, dict):

        raise ToolDispatchError(
            f"Arguments for '{tool_name}' "
            f"must be a JSON object."
        )

    # --------------------------------------------------------
    # Get Pydantic schema
    # --------------------------------------------------------

    schema = TOOL_SCHEMAS.get(
        tool_name
    )

    if schema is None:

        raise ToolDispatchError(
            f"No argument schema registered "
            f"for tool '{tool_name}'"
        )

    # --------------------------------------------------------
    # Validate arguments
    # --------------------------------------------------------

    try:

        validated = schema(
            **raw_args
        )

    except ValidationError as e:

        raise ToolDispatchError(
            f"Invalid arguments for "
            f"'{tool_name}': {e}"
        ) from e

    # --------------------------------------------------------
    # Get Python function
    # --------------------------------------------------------

    function = TOOL_FUNCTIONS[
        tool_name
    ]

    # --------------------------------------------------------
    # High-impact tool handling
    # --------------------------------------------------------
    #
    # request_rollback only creates an approval request.
    # It does NOT execute the rollback.
    #
    # The actual execution happens later through the
    # human approval flow.
    #
    # --------------------------------------------------------

    if tool_name in HIGH_IMPACT_TOOLS:

        return function(
            **validated.model_dump()
        )

    # --------------------------------------------------------
    # Normal tool execution
    # --------------------------------------------------------

    return function(
        **validated.model_dump()
    )