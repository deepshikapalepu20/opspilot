from . import tools
from .schemas import TOOL_SCHEMAS
from pydantic import ValidationError


# Map each tool name to its actual Python function.
# Adding a new tool requires one entry here plus one schema in schemas.py.
TOOL_FUNCTIONS = {
    "query_metrics": tools.query_metrics,
    "search_logs": tools.search_logs,
    "get_deployments": tools.get_deployments,
    "search_incidents": tools.search_incidents,
    "retrieve_runbook": tools.retrieve_runbook,
    "create_incident_report": tools.create_incident_report,
    "request_rollback": tools.request_rollback,
}


# High-impact tools are handled by the approval layer later.
HIGH_IMPACT_TOOLS = {"request_rollback"}


class ToolDispatchError(Exception):
    pass


def ollama_tool_definitions() -> list[dict]:
    """
    Generate OpenAI-style function-calling definitions
    from the Pydantic schemas.
    """

    definitions = []

    for name, schema in TOOL_SCHEMAS.items():
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": TOOL_FUNCTIONS[name].__doc__
                    or f"Call {name}",
                    "parameters": schema.model_json_schema(),
                },
            }
        )

    return definitions


def dispatch(tool_name: str, raw_args: dict) -> dict:
    """
    Validate tool arguments using the corresponding Pydantic schema,
    then call the registered Python function.
    """

    if tool_name not in TOOL_FUNCTIONS:
        raise ToolDispatchError(
            f"Unknown tool '{tool_name}'"
        )

    schema = TOOL_SCHEMAS[tool_name]

    try:
        validated = schema(**raw_args)
    except ValidationError as e:
        raise ToolDispatchError(
            f"Invalid arguments for {tool_name}: {e}"
        )

    function = TOOL_FUNCTIONS[tool_name]

    return function(**validated.model_dump())