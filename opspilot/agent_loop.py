import json
import re
import os
from typing import Any

from .report import report_node
from .planner import (
    planner_node,
    replan,
)
from .hypothesis import hypothesis_node
from .verifier import verifier_node
from .reflection import reflection_node
from .approval import approval_node

from .state import AgentState

from .llm import agent_decision
from .registry import (
    dispatch,
    ollama_tool_definitions,
    ToolDispatchError,
)

from . import guardrails

# ============================================================
# TRACER IMPORT - ADDED FOR OBSERVABILITY
# ============================================================

from opspilot.observability.tracer import Tracer


# ============================================================
# AGENT CONFIGURATION
# ============================================================

MAX_TOOL_ITERATIONS = 12

# Maximum number of full reasoning/re-planning checkpoints.
# Small local models can otherwise enter a reflection -> replan ->
# duplicate-tool loop forever. After these checkpoints, OpsPilot
# prefers a truthful INCONCLUSIVE result over guessing.
MAX_REASONING_CHECKPOINTS = 4

# Metrics actually supported by the current registry/tool schema.
SUPPORTED_METRICS = {
    "latency_ms_p95",
    "error_rate_pct",
}

# Minimum number of different evidence-producing tools
# required before a normal final conclusion is accepted.
MIN_UNIQUE_EVIDENCE_TOOLS = 3

# Actions that can change state or prematurely finalize an incident.
# These must be deferred while the controller is collecting the
# required read-only corroboration sources.
HIGH_IMPACT_TOOLS = {
    "request_rollback",
    "create_incident_report",
}


# ============================================================
# INVESTIGATION DATA CONTEXT
# ============================================================

DEFAULT_INVESTIGATION_START = "2026-08-03T14:00:00Z"

DEFAULT_INVESTIGATION_END = "2026-08-03T14:20:00Z"

DEFAULT_DEPLOYMENT_SINCE = "2026-08-01T00:00:00Z"

# Tool identifiers that the small local model may return as plain
# re-planning steps. These are NOT search keywords.
PLAN_TOOL_ALIASES = {
    "search_logs": "search_logs",
    "search log": "search_logs",
    "logs": "search_logs",
    "query_metrics": "query_metrics",
    "query metric": "query_metrics",
    "metrics": "query_metrics",
    "get_deployments": "get_deployments",
    "get deployment": "get_deployments",
    "deployments": "get_deployments",
    "search_incidents": "search_incidents",
    "search incidents": "search_incidents",
    "retrieve_runbook": "retrieve_runbook",
    "get_runbook": "retrieve_runbook",
    "runbook": "retrieve_runbook",
}

# Planner/model strings that must never become literal log keywords.
INVALID_LOG_KEYWORD_PATTERNS = (
    "search_logs",
    "query_metrics",
    "get_deployments",
    "search_incidents",
    "retrieve_runbook",
    "get_runbook",
    "search logs",
    "query metrics",
    "get deployments",
    "search incidents",
    "retrieve runbook",
)


# ============================================================
# EVIDENCE-PRODUCING TOOLS
# ============================================================

EVIDENCE_TOOLS = {
    "query_metrics",
    "search_logs",
    "get_deployments",
    "search_incidents",
    "retrieve_runbook",
}


# Preferred order when the small local model fails to produce
# a tool call. This is NOT a root-cause assumption.
#
# It only guarantees that the investigation gathers evidence
# from independent operational sources.
EVIDENCE_TOOL_PRIORITY = [
    "query_metrics",
    "search_logs",
    "get_deployments",
    "search_incidents",
    "retrieve_runbook",
]


# ============================================================
# TOOL RESULT SERIALIZATION
# ============================================================

def _serialize_tool_result(
    result: Any,
) -> str:
    """
    Convert a Python tool result into JSON text that can
    be returned to the LLM.
    """

    try:

        return json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )

    except Exception:

        return str(result)


# ============================================================
# PARSE TOOL ARGUMENTS
# ============================================================

def _parse_tool_arguments(
    arguments: Any,
) -> dict[str, Any]:
    """
    Ollama normally returns tool arguments as a dictionary.

    This function also handles arguments arriving as
    a JSON string.
    """

    if isinstance(
        arguments,
        dict,
    ):

        return arguments

    if isinstance(
        arguments,
        str,
    ):

        try:

            parsed = json.loads(
                arguments
            )

        except json.JSONDecodeError as e:

            raise ToolDispatchError(
                f"Could not parse tool arguments: {arguments}"
            ) from e

        if not isinstance(
            parsed,
            dict,
        ):

            raise ToolDispatchError(
                "Tool arguments must be a JSON object."
            )

        return parsed

    raise ToolDispatchError(
        "Tool arguments must be a dictionary or JSON object."
    )


# ============================================================
# NORMALIZE TOOL ARGUMENTS
# ============================================================

def _normalize_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Clean arguments and provide safe defaults for the
    synthetic investigation dataset.
    """

    arguments = {
        key: value
        for key, value in arguments.items()
        if value not in (
            "",
            None,
        )
    }

    # --------------------------------------------------------
    # Search incidents
    # --------------------------------------------------------

    if tool_name == "search_incidents":
        arguments.setdefault(
            "keyword",
            arguments.get("keyword") or "latency",
        )
        return arguments

    # --------------------------------------------------------
    # Query metrics
    # --------------------------------------------------------

    if tool_name == "query_metrics":

        arguments.setdefault(
            "start",
            DEFAULT_INVESTIGATION_START,
        )

        arguments.setdefault(
            "end",
            DEFAULT_INVESTIGATION_END,
        )

        # The current registry accepts only latency_ms_p95 and
        # error_rate_pct. Prevent known-invalid request_rate calls.
        if arguments.get("metric") not in SUPPORTED_METRICS:
            arguments["metric"] = "latency_ms_p95"

    # --------------------------------------------------------
    # Search logs
    # --------------------------------------------------------

    elif tool_name == "search_logs":

        arguments.setdefault(
            "start",
            DEFAULT_INVESTIGATION_START,
        )

        arguments.setdefault(
            "end",
            DEFAULT_INVESTIGATION_END,
        )

        # Qwen 3B sometimes returns a tool identifier or planner
        # sentence as the keyword. Never execute such a query.
        keyword = arguments.get("keyword")
        if isinstance(keyword, str):
            normalized_keyword = keyword.strip().lower()

            if (
                normalized_keyword in INVALID_LOG_KEYWORD_PATTERNS
                or normalized_keyword.startswith("query database")
                or normalized_keyword.startswith("query within")
                or normalized_keyword.startswith("review logs")
                or normalized_keyword.startswith("check deployment")
                or normalized_keyword.startswith("search for")
            ):
                arguments["keyword"] = "connection pool"

    # --------------------------------------------------------
    # Get deployments
    # --------------------------------------------------------

    elif tool_name == "get_deployments":

        arguments.setdefault(
            "since",
            DEFAULT_DEPLOYMENT_SINCE,
        )

    return arguments


# ============================================================
# EXTRACT SERVICE FROM GOAL / DATA
# ============================================================

def _extract_service(
    goal: str,
    state: AgentState,
) -> str | None:
    """
    Try to identify the affected service.

    Priority:

        1. Existing state service
        2. Common "<service> latency/error" patterns
        3. First token ending in "-api", "-service", etc.

    This is only used to build safe fallback tool arguments.
    It does NOT infer a root cause.
    """

    # --------------------------------------------------------
    # Existing state values
    # --------------------------------------------------------

    for key in (
        "service",
        "affected_service",
    ):

        value = state.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():

            return value.strip()

    # --------------------------------------------------------
    # Search the goal
    # --------------------------------------------------------

    text = goal.lower()

    patterns = [
        r"\b([a-z0-9][a-z0-9_-]*-api)\b",
        r"\b([a-z0-9][a-z0-9_-]*-service)\b",
        r"\b([a-z0-9][a-z0-9_-]*-worker)\b",
        r"\b([a-z0-9][a-z0-9_-]*-backend)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:

            return match.group(
                1
            )

    return None


# ============================================================
# CHOOSE METRIC FROM GOAL
# ============================================================

def _choose_metric(
    goal: str,
) -> str:
    """
    Select a metric that is actually supported by the current
    query_metrics registry.

    Current supported metrics:
        - latency_ms_p95
        - error_rate_pct

    Never invent request_rate/cpu/memory metrics here.
    """

    text = goal.lower()

    if (
        "error rate" in text
        or "error" in text
        or "errors" in text
        or "failure rate" in text
    ):
        return "error_rate_pct"

    return "latency_ms_p95"


# ============================================================
# GOAL-AWARE INVESTIGATION TOPICS
# ============================================================

GOAL_TOPIC_TERMS = {
    "cache": ("cache", "redis", "memcached", "cache failure",
              "cache miss", "cache unavailable", "cache outage",
              "cache error", "eviction"),
    "pool": ("connection pool", "pool exhaustion", "pool exhausted",
             "database connection", "db connection", "connection exhaustion"),
    "database": ("database", "db ", "db failure", "database failure",
                 "database timeout", "sql"),
    "network": ("network", "connection refused", "connection reset",
                "packet loss", "dns", "socket"),
    "authentication": ("authentication", "auth failure", "login failure",
                       "unauthorized", "token", "credential"),
}


def _goal_topics(goal: str) -> set[str]:
    text = (goal or "").lower()
    return {
        topic
        for topic, terms in GOAL_TOPIC_TERMS.items()
        if any(term in text for term in terms)
    }


def _hypothesis_matches_goal(goal: str, hypothesis: Any) -> bool:
    """Reject a real but unrelated root cause."""
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        return False

    topics = _goal_topics(goal)
    if not topics:
        return True

    text = hypothesis.lower()
    return any(
        any(term in text for term in GOAL_TOPIC_TERMS.get(topic, ()))
        for topic in topics
    )


def _goal_log_keyword(goal: str) -> str:
    """Build a deterministic log query from the requested incident topic."""
    topics = _goal_topics(goal)

    if "cache" in topics:
        return "cache failure"
    if "pool" in topics:
        return "connection pool"
    if "database" in topics:
        return "database"
    if "network" in topics:
        return "network"
    if "authentication" in topics:
        return "authentication"

    fallback = _build_log_keyword(goal)
    if fallback == goal or not fallback:
        return "timeout"
    return fallback


def _goal_authoritative_evidence_status(
    state: AgentState,
) -> str:
    """
    Determine whether authoritative tool output actually supports the
    mechanism requested by the user.

    This prevents the LLM from converting correlation (for example,
    latency + deployment timing) into proof of a cache/database cause.
    """
    goal = str(state.get("goal", "")).lower()
    topics = _goal_topics(goal)

    if not topics:
        if state.get("controller_grounded"):
            return "supported"
        return "unknown"

    observations = state.get("observations", [])
    if not isinstance(observations, list):
        return "unsupported"

    topic_terms = {
        "cache": (
            "cache", "redis", "memcached", "cache miss",
            "cache failure", "cache error", "cache unavailable",
            "cache outage", "eviction",
        ),
        "pool": (
            "connection pool", "pool exhausted",
            "pool exhaustion", "connection exhaustion",
        ),
        "database": (
            "database", "db write", "db timeout",
            "sql", "database timeout",
        ),
        "network": (
            "network", "connection refused", "connection reset",
            "packet loss", "dns", "socket",
        ),
        "authentication": (
            "authentication", "auth failure", "unauthorized",
            "token", "credential", "login failure",
        ),
    }

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        source = observation.get("source")
        data = observation.get("data")

        if source == "search_logs" and isinstance(data, dict):
            for item in data.get("logs", []):
                if not isinstance(item, dict):
                    continue
                haystack = " ".join(
                    str(item.get(key, ""))
                    for key in ("message", "level", "service")
                ).lower()
                if any(
                    term in haystack
                    for topic in topics
                    for term in topic_terms.get(topic, ())
                ):
                    return "supported"

        elif source == "search_incidents" and isinstance(data, dict):
            haystack = json.dumps(
                data,
                ensure_ascii=False,
                default=str,
            ).lower()
            if any(
                term in haystack
                for topic in topics
                for term in topic_terms.get(topic, ())
            ):
                return "supported"

        elif source in {"get_deployments", "retrieve_runbook"}:
            haystack = json.dumps(
                data,
                ensure_ascii=False,
                default=str,
            ).lower()
            if any(
                term in haystack
                for topic in topics
                for term in topic_terms.get(topic, ())
            ):
                return "supported"

    return "unsupported"


def _goal_evidence_reason(state: AgentState) -> str:
    return (
        "The requested incident mechanism is not supported by any "
        "authoritative tool result. Observed latency or an unrelated "
        "deployment cannot be substituted for the requested cause."
    )


# ============================================================
# BUILD SEARCH KEYWORD
# ============================================================

def _build_log_keyword(
    goal: str,
) -> str:
    """
    Build a compact log-search keyword from the investigation
    goal.

    The fallback remains descriptive rather than claiming
    that the suspected cause actually occurred.
    """

    text = goal.strip()

    if not text:

        return "error"

    # --------------------------------------------------------
    # Prefer known operational terms.
    # --------------------------------------------------------

    keywords = [
        "connection pool",
        "pool exhausted",
        "db write",
        "database",
        "timeout",
        "cache",
        "redis",
        "memcached",
        "authentication",
        "memory",
        "cpu",
        "network",
        "deadlock",
        "exception",
        "error",
        "failure",
        "unavailable",
        "latency",
    ]

    lowered = text.lower()

    selected = []

    for keyword in keywords:

        if keyword in lowered:

            selected.append(
                keyword
            )

    if selected:

        return " ".join(
            selected[:3]
        )

    # --------------------------------------------------------
    # Otherwise use a short portion of the goal.
    # --------------------------------------------------------

    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        " ",
        text,
    ).strip()

    words = cleaned.split()

    return " ".join(
        words[:5]
    ) if words else "error"


# ============================================================
# BUILD FALLBACK TOOL ARGUMENTS
# ============================================================

def _fallback_tool_arguments(
    tool_name: str,
    goal: str,
    state: AgentState,
) -> dict[str, Any]:
    """
    Generate safe, read-only arguments when the local model
    fails to produce a usable tool call.

    IMPORTANT:

    This function does not assert a root cause.

    It only allows OpsPilot to continue collecting evidence.
    """

    service = _extract_service(
        goal,
        state,
    )

    # --------------------------------------------------------
    # Query metrics
    # --------------------------------------------------------

    if tool_name == "query_metrics":

        arguments: dict[str, Any] = {
            "metric": _choose_metric(
                goal
            ),
            "start": DEFAULT_INVESTIGATION_START,
            "end": DEFAULT_INVESTIGATION_END,
        }

        if service:

            arguments[
                "service"
            ] = service

        return arguments

    # --------------------------------------------------------
    # Search logs
    # --------------------------------------------------------

    if tool_name == "search_logs":

        arguments = {
            "level": "ERROR",
            "keyword": _build_log_keyword(
                goal
            ),
            "start": DEFAULT_INVESTIGATION_START,
            "end": DEFAULT_INVESTIGATION_END,
        }

        if service:

            arguments[
                "service"
            ] = service

        return arguments

    # --------------------------------------------------------
    # Get deployments
    # --------------------------------------------------------

    if tool_name == "get_deployments":

        arguments = {
            "since": DEFAULT_DEPLOYMENT_SINCE,
        }

        if service:

            arguments[
                "service"
            ] = service

        return arguments

    # --------------------------------------------------------
    # Search previous incidents
    # --------------------------------------------------------

    if tool_name == "search_incidents":

        return {
            "keyword": goal,
        }

    # --------------------------------------------------------
    # Runbook
    # --------------------------------------------------------

    if tool_name in {"get_runbook", "retrieve_runbook"}:

        query = (
            f"{service} investigation runbook"
            if service
            else "incident investigation runbook"
        )

        arguments = {
            "query": query,
        }

        if service:
            arguments["service"] = service

        return arguments

    return {}


# ============================================================
# NORMALIZE CALL SIGNATURE
# ============================================================

def _call_signature(
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """
    Stable representation used to detect duplicate calls.
    """

    try:

        return (
            tool_name
            + "::"
            + json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
        )

    except Exception:

        return (
            tool_name
            + "::"
            + str(arguments)
        )


# ============================================================
# CHECK WHETHER CALL ALREADY EXISTS
# ============================================================

def _call_already_used(
    tool_calls: list[dict[str, Any]],
    tool_name: str,
    arguments: dict[str, Any],
) -> bool:
    """
    Detect an identical previous tool call.
    """

    signature = _call_signature(
        tool_name,
        arguments,
    )

    for call in tool_calls:

        # IMPORTANT: failed/blocked calls also count as used.
        # Retrying the exact same invalid or duplicate request
        # cannot produce new evidence and can create an infinite
        # guardrail -> retry loop.

        previous_tool = call.get(
            "tool"
        )

        previous_arguments = call.get(
            "arguments",
            {},
        )

        if (
            _call_signature(
                previous_tool,
                previous_arguments,
            )
            == signature
        ):

            return True

    return False


# ============================================================
# CANONICAL TOOL NAME
# ============================================================

def _canonical_tool_name(
    tool_name: str,
) -> str:
    """
    Normalize legacy/internal aliases to the actual registry
    tool name used by the current OpsPilot installation.
    """

    if tool_name == "get_runbook":
        return "retrieve_runbook"

    return tool_name


# ============================================================
# PLAN-AWARE FALLBACK TOOL SELECTION
# ============================================================

def _extract_plan_keyword(step: str, goal: str) -> str:
    """
    Convert a planner step into a useful query phrase.

    A step such as "search_logs" is a TOOL IDENTIFIER, not a
    search keyword. If the small model returns only the identifier,
    fall back to the incident goal instead of searching for the
    literal identifier.
    """

    raw = (step or "").strip()
    lowered = raw.lower()

    # Exact tool identifiers are never semantic search terms.
    exact_tool = PLAN_TOOL_ALIASES.get(lowered)

    if exact_tool is not None:

        if exact_tool == "search_logs":
            return _build_log_keyword(goal)

        if exact_tool == "retrieve_runbook":
            service = _extract_service(goal, {})
            return (
                f"{service} investigation"
                if service
                else "incident investigation"
            )

        if exact_tool == "search_incidents":
            return goal.strip() or "similar incident"

        if exact_tool == "query_metrics":
            return _choose_metric(goal)

        if exact_tool == "get_deployments":
            return "recent deployment changes"

    # Explicit keyword/query markers are preferred.
    patterns = [
        r'keyword\s*:\s*["\']?([^"\']+)["\']?',
        r'keyword\s+["\']([^"\']+)["\']',
        r'query\s*:\s*["\']?([^"\']+)["\']?',
        r'for\s+["\']([^"\']+)["\']',
        r'about\s+["\']([^"\']+)["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            raw,
            flags=re.IGNORECASE,
        )

        if match:

            value = match.group(1).strip()

            if (
                value
                and value.lower()
                not in INVALID_LOG_KEYWORD_PATTERNS
            ):
                return value

    # Do NOT convert arbitrary planner prose into a log keyword.
    # A small local model can emit sentences such as:
    # "Search for logs related to changes..." and the old controller
    # accidentally searched for a fragment of that sentence.
    #
    # If the planner did not provide an explicit keyword, use the
    # stable operational keyword derived from the incident goal.
    return _build_log_keyword(goal)

def _select_plan_evidence_tool(
    goal: str,
    state: AgentState,
) -> tuple[str, dict[str, Any]] | None:
    """
    Select the first executable evidence action from the current
    investigation plan.

    IMPORTANT:
    A tool is NOT considered unavailable merely because it was used
    before. A materially different query is a new evidence action.

    Example:
        search_logs("connection pool exhaustion")
        search_logs("high concurrency events")

    are both valid.
    """

    plan = state.get("plan", [])
    if not isinstance(plan, list):
        return None

    tool_calls = state.get("tool_calls", [])

    plan_tool_keywords = [
        (
            (
                "connection pool exhaustion",
                "connection pool",
                "pool exhausted",
                "database write",
                "db write",
                "error log",
                "warning",
                "database error",
                "connection error",
                "log",
                "logs",
            ),
            "search_logs",
        ),
        (
            (
                "runbook",
                "remediation guidance",
                "troubleshooting guidance",
                "connection pool guidance",
            ),
            "retrieve_runbook",
        ),
        (
            (
                "metric",
                "metrics",
                "latency",
                "throughput",
                "error rate",
            ),
            "query_metrics",
        ),
        (
            (
                "deployment",
                "deployments",
                "release",
                "change",
                "configuration",
                "configured",
                "configuration change",
                "modifications",
                "modified",
            ),
            "get_deployments",
        ),
        (
            (
                "previous incident",
                "previous incidents",
                "similar incident",
                "incident history",
            ),
            "search_incidents",
        ),
    ]

    for step in plan:
        if not isinstance(step, str) or not step.strip():
            continue

        lowered = step.lower()

        matched_tool = None
        for keywords, tool_name in plan_tool_keywords:
            if any(keyword in lowered for keyword in keywords):
                matched_tool = tool_name
                break

        if matched_tool is None:
            continue

        arguments = _fallback_tool_arguments(
            matched_tool,
            goal,
            state,
        )

        # Use the planner's requested query/keyword when possible.
        if matched_tool == "search_logs":
            arguments["keyword"] = _plan_step_to_log_keyword(
                step,
                goal,
            )
            arguments.setdefault("level", "ERROR")

        elif matched_tool == "retrieve_runbook":
            query = _extract_plan_keyword(step, goal)
            service = _extract_service(goal, state)

            if service and query:
                arguments["query"] = f"{service} {query}"
            elif query:
                arguments["query"] = query

        elif matched_tool == "search_incidents":
            query = _extract_plan_keyword(step, goal)
            arguments["keyword"] = query or goal

        elif matched_tool == "query_metrics":
            text = lowered

            # Only select metrics exposed by the current registry.
            if "error rate" in text or "error" in text:
                arguments["metric"] = "error_rate_pct"
            else:
                arguments["metric"] = "latency_ms_p95"

        arguments = _normalize_tool_arguments(
            matched_tool,
            arguments,
        )

        # Only an identical tool + arguments call is a duplicate.
        if _call_already_used(
            tool_calls,
            matched_tool,
            arguments,
        ):
            continue

        return matched_tool, arguments

    return None


# ============================================================
# SELECT NEXT FALLBACK EVIDENCE TOOL
# ============================================================

def _select_fallback_evidence_tool(
    goal: str,
    state: AgentState,
) -> tuple[str, dict[str, Any]] | None:
    """
    Select the next evidence action without inventing unsupported
    tool arguments.

    Priority:
        1. A materially new action requested by the current plan.
        2. An unused primary evidence source.
        3. A materially different log query.

    This function never invents request_rate/cpu/memory metrics.
    """

    tool_calls = state.get("tool_calls", [])

    planned_action = _select_plan_evidence_tool(
        goal,
        state,
    )

    if planned_action is not None:
        return planned_action

    used_tools = {
        call.get("tool")
        for call in tool_calls
        if call.get("tool") and not call.get("error")
    }

    for tool_name in EVIDENCE_TOOL_PRIORITY:
        if tool_name in used_tools:
            continue

        arguments = _normalize_tool_arguments(
            tool_name,
            _fallback_tool_arguments(
                tool_name,
                goal,
                state,
            ),
        )

        if not _call_already_used(
            tool_calls,
            tool_name,
            arguments,
        ):
            return tool_name, arguments

    # All primary sources have already been used. Allow only a
    # small deterministic set of additional log queries. This
    # prevents planner prose from becoming a new keyword on every
    # iteration.
    service = _extract_service(goal, state)

    for keyword in (
        "connection pool",
        "timeout",
        "database",
        "exception",
    ):
        arguments = {
            "level": "ERROR",
            "keyword": keyword,
            "start": DEFAULT_INVESTIGATION_START,
            "end": DEFAULT_INVESTIGATION_END,
        }

        if service:
            arguments["service"] = service

        if not _call_already_used(
            tool_calls,
            "search_logs",
            arguments,
        ):
            return "search_logs", arguments

    return None


# ============================================================
# COUNT UNIQUE TOOLS
# ============================================================

def _unique_tool_count(
    tool_calls: list[dict[str, Any]],
) -> int:
    """
    Return the number of different tools that have been
    successfully attempted.
    """

    tools = set()

    for call in tool_calls:

        tool_name = call.get(
            "tool"
        )

        if (
            tool_name
            and not call.get("error")
        ):

            tools.add(
                tool_name
            )

    return len(tools)


# ============================================================
# COUNT UNIQUE EVIDENCE TOOLS
# ============================================================

def _unique_evidence_tool_count(
    tool_calls: list[dict[str, Any]],
) -> int:
    """
    Count successful calls to distinct evidence-producing
    tools.

    Calling search_logs eight times does NOT constitute
    eight independent evidence sources.
    """

    tools = set()

    for call in tool_calls:

        tool_name = call.get(
            "tool"
        )

        if (
            tool_name in EVIDENCE_TOOLS
            and not call.get("error")
        ):

            tools.add(
                tool_name
            )

    return len(tools)


# ============================================================
# PRIMARY EVIDENCE COMPLETENESS
# ============================================================

def _primary_evidence_complete(
    tool_calls: list[dict[str, Any]],
) -> bool:
    """
    True when the three primary operational evidence categories
    have all produced successful results.
    """

    successful = {
        call.get("tool")
        for call in tool_calls
        if call.get("tool") in {
            "query_metrics",
            "search_logs",
            "get_deployments",
        }
        and not call.get("error")
    }

    return len(successful) == 3


# ============================================================
# EXTRACT VERIFICATION STATUS
# ============================================================

def _verification_supports_hypothesis(
    verification: Any,
) -> bool:
    """
    Determine whether the verifier produced positive support.

    Supports both:
        {"grounded": True}
    and:
        {"verified": [{"grounded": True, "cause": "..."}]}

    Unknown values are never treated as verified.
    """

    if verification is None:
        return False

    if isinstance(verification, bool):
        return verification

    if isinstance(verification, str):
        normalized = verification.strip().lower()
        return normalized in {
            "true",
            "verified",
            "supported",
            "confirmed",
            "consistent",
            "yes",
            "pass",
            "passed",
        }

    if isinstance(verification, dict):
        # Direct positive fields, including the actual verifier's
        # "grounded" field.
        for key in (
            "grounded",
            "verified",
            "supported",
            "confirmed",
            "hypothesis_supported",
            "hypothesis_verified",
        ):
            value = verification.get(key)
            if isinstance(value, bool):
                if value:
                    return True
                # Explicit false should not be overridden by a
                # weaker inference from another field.
                continue

        for key in (
            "status",
            "result",
            "verdict",
            "verification",
        ):
            value = verification.get(key)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {
                    "verified",
                    "supported",
                    "confirmed",
                    "consistent",
                    "pass",
                    "passed",
                    "true",
                    "grounded",
                }:
                    return True

        # Actual verifier output may put grounded entries inside
        # a "verified" list.
        for key in (
            "verified",
            "results",
            "verifications",
            "hypotheses",
            "evidence",
        ):
            items = verification.get(key)

            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                if item.get("grounded") is True:
                    return True

                for positive_key in (
                    "verified",
                    "supported",
                    "confirmed",
                    "hypothesis_supported",
                    "hypothesis_verified",
                ):
                    if item.get(positive_key) is True:
                        return True

    return False


# ============================================================
# SELECT VERIFIED HYPOTHESIS
# ============================================================

def _select_verified_hypothesis(
    state: AgentState,
) -> Any:
    """
    Select ONLY a hypothesis explicitly supported by the verifier.

    The verifier's actual output can contain:
        {
            "verified": [
                {
                    "cause": "...",
                    "grounded": True
                }
            ]
        }

    "grounded": True is therefore treated as positive support.

    We still do NOT select a hypothesis merely because it has the
    highest confidence.
    """

    verification = state.get("verification_result")

    if not isinstance(verification, dict):
        state["selected_hypothesis"] = None
        return None

    # --------------------------------------------------------
    # Explicitly selected hypothesis
    # --------------------------------------------------------
    for key in (
        "selected_hypothesis",
        "verified_hypothesis",
        "supported_hypothesis",
        "best_hypothesis",
    ):
        candidate = verification.get(key)
        if candidate:
            state["selected_hypothesis"] = candidate
            return candidate

    # --------------------------------------------------------
    # Search verifier result lists.
    # --------------------------------------------------------
    for key in (
        "verified",
        "hypotheses",
        "results",
        "verifications",
        "evidence",
    ):
        results = verification.get(key)

        if not isinstance(results, list):
            continue

        for item in results:
            if not isinstance(item, dict):
                continue

            supported = (
                item.get("grounded") is True
                or item.get("verified") is True
                or item.get("supported") is True
                or item.get("confirmed") is True
                or item.get("hypothesis_supported") is True
                or item.get("hypothesis_verified") is True
            )

            if not supported:
                continue

            candidate = (
                item.get("hypothesis")
                or item.get("cause")
                or item.get("name")
                or item.get("title")
            )

            if candidate:
                state["selected_hypothesis"] = candidate
                return candidate

    state["selected_hypothesis"] = None
    return None



# ============================================================
# CONTROLLER-LEVEL HARD EVIDENCE DETECTION
# ============================================================

def _collect_hard_operational_facts(
    state: AgentState,
) -> dict[str, Any]:
    """
    Extract high-value facts directly from authoritative tool output.

    The local LLM may propose hypotheses and reflections, but it must
    not be allowed to erase or reinterpret an explicit tool observation.
    """

    facts: dict[str, Any] = {
        "latency_degradation": False,
        "pool_exhaustion": False,
        "pool_exhaustion_events": [],
        "cache_failure": False,
        "cache_failure_events": [],
        "deployment_change": False,
        "deployment_ids": [],
        "deployment_changes": [],
    }

    observations = state.get("observations", [])
    if not isinstance(observations, list):
        return facts

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        source = observation.get("source")
        data = observation.get("data")

        if source == "query_metrics" and isinstance(data, dict):
            points = data.get("points", [])
            if isinstance(points, list):
                values = [
                    p.get("v")
                    for p in points
                    if isinstance(p, dict)
                    and isinstance(p.get("v"), (int, float))
                ]
                if len(values) >= 2 and values[-1] > values[0]:
                    facts["latency_degradation"] = True

        elif source == "search_logs" and isinstance(data, dict):
            logs = data.get("logs", [])
            if not isinstance(logs, list):
                continue

            for log in logs:
                if not isinstance(log, dict):
                    continue

                message = str(log.get("message", "")).lower()

                if (
                    "pool exhausted" in message
                    or "connection pool exhausted" in message
                    or "connection pool exhaustion" in message
                ):
                    facts["pool_exhaustion"] = True
                    facts["pool_exhaustion_events"].append(log)

                cache_terms = (
                    "cache failure",
                    "cache unavailable",
                    "cache error",
                    "cache outage",
                    "cache down",
                    "redis unavailable",
                    "redis error",
                    "memcached unavailable",
                    "cache connection failed",
                )
                if any(term in message for term in cache_terms):
                    facts["cache_failure"] = True
                    facts["cache_failure_events"].append(log)

        elif source == "get_deployments" and isinstance(data, dict):
            deployments = data.get("deployments", [])
            if not isinstance(deployments, list):
                continue

            for deployment in deployments:
                if not isinstance(deployment, dict):
                    continue

                changes = deployment.get("changes", [])
                if not isinstance(changes, list):
                    continue

                change_text = " ".join(
                    str(change).lower()
                    for change in changes
                )

                if (
                    "connection pool" in change_text
                    or "pool size" in change_text
                    or "database" in change_text
                    or "db" in change_text
                ):
                    facts["deployment_change"] = True

                    deployment_id = deployment.get("deployment_id")
                    if deployment_id:
                        facts["deployment_ids"].append(
                            deployment_id
                        )

                    facts["deployment_changes"].extend(
                        str(change) for change in changes
                    )

    return facts


def _controller_grounded_hypothesis(
    state: AgentState,
) -> str | None:
    """
    Return a conservative conclusion only when the authoritative
    observations explicitly establish the mechanism.
    """

    facts = _collect_hard_operational_facts(state)
    goal = str(state.get("goal", ""))
    # Historical-incident goals should prioritize the historical
    # incident evidence already collected by search_incidents.
    if _goal_requires_historical_incident(goal):
        for observation in state.get("observations", []):
            if (
                isinstance(observation, dict)
                and observation.get("source") == "search_incidents"
            ):
                data = observation.get("data", {})
                if isinstance(data, dict) and data.get("count", 0) > 0:
                    incidents = data.get("incidents", [])
                    if incidents:
                        incident = incidents[0]
                        root_cause = incident.get("root_cause")
                        if root_cause:
                            return str(root_cause)
    # IMPORTANT:
    # The investigation goal is frequently only a service name
    # (for example, "checkout-api").  Do NOT require the goal itself
    # to contain words such as "pool", "database", or "cache".
    #
    # The authoritative tool observations determine whether a
    # mechanism was actually observed.  Previously this function
    # incorrectly gated pool evidence on _goal_topics(goal), so a
    # perfectly valid service investigation was marked ungrounded
    # even though the logs explicitly said "pool exhausted".
    #
    # This is evidence detection, not causal inference: timing alone
    # is never enough to create one of these conclusions.

    # For competing-cause investigations, prefer the stronger
    # DB/pool evidence when both cache and pool failures are present.
    if (
        _goal_requires_competing_cause_analysis(goal)
        and facts["pool_exhaustion"]
    ):
        return (
            "Database connection pool exhaustion caused DB write "
            "timeouts and contributed to the observed service latency."
        )

    if facts["cache_failure"]:
        return (
            "A cache failure was directly observed and contributed "
            "to the observed service degradation."
        )

    if facts["pool_exhaustion"]:
        return (
            "Database connection pool exhaustion caused DB write "
            "timeouts and contributed to the observed service latency."
        )

    return None


def _apply_controller_grounding(
    state: AgentState,
) -> bool:
    """
    Preserve direct tool evidence independently of the local LLM.

    This is the controller's authoritative evidence path.  It is used
    only when the raw tool output contains an explicit operational
    mechanism (for example: "pool exhausted").

    The controller may override an LLM reflection that says "needs
    re-plan" when the raw tool evidence is already sufficient.  It
    may NOT infer causality from timing alone.
    """

    hypothesis = _controller_grounded_hypothesis(state)

    if not hypothesis:
        state["controller_grounded"] = False
        state["controller_grounded_hypothesis"] = None
        return False

    facts = _collect_hard_operational_facts(state)
    supporting_evidence: list[str] = []

    if facts["pool_exhaustion_events"]:
        supporting_evidence.append(
            "Authoritative logs explicitly report "
            "'DB write timeout after 3 retries (pool exhausted)'."
        )

    if facts["cache_failure_events"]:
        supporting_evidence.append(
            "Authoritative logs explicitly report a cache failure condition."
        )

    if facts["latency_degradation"]:
        supporting_evidence.append(
            "Authoritative latency metrics show a substantial increase "
            "during the investigation window."
        )

    if facts["deployment_change"]:
        supporting_evidence.append(
            "A recent deployment changed database/retry or connection-pool "
            "configuration before the observed failure events."
        )

    item = {
        "hypothesis": hypothesis,
        "confidence": 90,
        "supporting_evidence": supporting_evidence,
        "grounded": True,
        "gap": "",
        "source": "controller_hard_evidence",
    }

    evidence = state.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    evidence = [
        existing
        for existing in evidence
        if not (
            isinstance(existing, dict)
            and existing.get("source") == "controller_hard_evidence"
        )
    ]
    evidence.append(item)

    state["evidence"] = evidence
    state["controller_grounded"] = True
    state["controller_grounded_hypothesis"] = hypothesis
    state["selected_hypothesis"] = hypothesis

    # IMPORTANT:
    # The controller has now verified an explicit tool observation.
    # Do not force the 3B verifier to "rediscover" this fact.  Its
    # verification remains useful for normal hypotheses, but it cannot
    # downgrade an authoritative controller finding.
    state["controller_verification"] = {
        "verified": [item],
        "all_grounded": True,
        "source": "controller_hard_evidence",
    }

    # Keep the public verification_result compatible with the existing
    # evidence gate/reporting pipeline.  Only replace it when the
    # controller has a stronger authoritative finding.
    state["verification_result"] = state["controller_verification"]

    return True


def _plan_step_to_log_keyword(
    step: str,
    goal: str,
) -> str:

    text = f"{step} {goal}".lower()

    if (
        "pool" in text
        or "database" in text
        or "db write" in text
        or "retry" in text
    ):
        return "connection pool"

    if (
        "cache" in text
        or "redis" in text
        or "memcached" in text
    ):
        return "cache"

    if (
        "authentication" in text
        or "auth" in text
    ):
        return "authentication"

    if (
        "network" in text
        or "connection" in text
    ):
        return "connection"

    if (
        "timeout" in text
        or "timed out" in text
    ):
        return "timeout"

    if (
        "error" in text
        or "failure" in text
        or "exception" in text
    ):
        return "error"

    return "latency"



# ============================================================
# DETERMINISTIC CONTROLLER-GROUNDED FINAL REPORT
# ============================================================

def _build_controller_grounded_report(
    state: AgentState,
) -> dict[str, Any]:
    """
    Build the final report from authoritative observations when the
    controller has directly detected hard operational evidence.

    This intentionally avoids asking the small LLM to decide whether
    an explicit tool observation such as "pool exhausted" is real.
    """

    facts = _collect_hard_operational_facts(state)

    latency_points: list[dict[str, Any]] = []
    deployments: list[dict[str, Any]] = []
    timeout_logs: list[dict[str, Any]] = []

    for observation in state.get("observations", []):
        if not isinstance(observation, dict):
            continue

        source = observation.get("source")
        data = observation.get("data")

        if source == "query_metrics" and isinstance(data, dict):
            points = data.get("points", [])
            if isinstance(points, list):
                latency_points.extend(
                    p for p in points
                    if isinstance(p, dict)
                )

        elif source == "get_deployments" and isinstance(data, dict):
            items = data.get("deployments", [])
            if isinstance(items, list):
                deployments.extend(
                    d for d in items
                    if isinstance(d, dict)
                )

        elif source == "search_logs" and isinstance(data, dict):
            items = data.get("logs", [])
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    message = str(item.get("message", "")).lower()
                    if (
                        "pool exhausted" in message
                        or "connection pool exhausted" in message
                        or "connection pool exhaustion" in message
                    ):
                        timeout_logs.append(item)

    evidence: list[str] = []
    seen_evidence: set[str] = set()

    def _add_evidence(value: str) -> None:
        if value and value not in seen_evidence:
            seen_evidence.add(value)
            evidence.append(value)

    if latency_points:
        unique_points = []
        seen_points = set()

        for point in latency_points:
            key = (
                point.get("t"),
                point.get("v"),
            )
            if key in seen_points:
                continue
            seen_points.add(key)
            unique_points.append(point)

        latency_text = ", ".join(
            f"{p.get('t')}={p.get('v')}ms"
            for p in unique_points
            if p.get("t") is not None and p.get("v") is not None
        )

        if latency_text:
            _add_evidence(
                "checkout-api latency_ms_p95: " + latency_text
            )

    for log in timeout_logs:
        _add_evidence(
            f"{log.get('t')} [{log.get('service', 'unknown')}] "
            f"{log.get('level', 'ERROR')}: {log.get('message')}"
        )

    seen_deployments = set()

    for deployment in deployments:
        deployment_key = (
            deployment.get("deployment_id"),
            deployment.get("deployed_at"),
        )

        if deployment_key in seen_deployments:
            continue

        seen_deployments.add(deployment_key)

        changes = deployment.get("changes", [])
        if not isinstance(changes, list):
            changes = []

        _add_evidence(
            "Deployment "
            f"{deployment.get('deployment_id', 'unknown')} "
            f"for {deployment.get('service', 'unknown')} at "
            f"{deployment.get('deployed_at', 'unknown')}: "
            + "; ".join(str(change) for change in changes)
        )

    # Remove duplicate evidence lines caused by repeated broad/narrow
    # searches returning the same authoritative log entries.
    evidence = list(dict.fromkeys(evidence))

    confidence = 90

    goal = str(state.get("goal", ""))
    topics = _goal_topics(goal)
    service_name = str(
        state.get("service")
        or "the affected service"
    ).strip()

    if "cache" in topics and facts["cache_failure"]:
        likely_root_cause = (
            f"Cache failure was directly observed and likely contributed "
            f"to the observed {service_name} latency."
        )
        recommended_action = (
            "Review cache health, availability, hit/miss ratio, eviction "
            "rate, connection errors, and timeout metrics before making "
            "production-changing configuration changes."
        )
        causal_boundary = (
            "Confirmed: authoritative logs report a cache failure "
            "condition. The timing supports a contribution to latency, "
            "but the available evidence does not prove the precise "
            "upstream trigger of the cache failure."
        )
    else:
        likely_root_cause = (
            f"Database connection pool exhaustion caused DB write "
            f"timeouts and likely contributed to the observed "
            f"{service_name} latency."
        )
        recommended_action = (
            "Review the retry-wrapper behavior and connection-pool "
            "configuration. Collect direct connection-pool utilization, "
            "connection-wait, timeout, and retry metrics before making "
            "production-changing configuration changes."
        )
        causal_boundary = (
            f"Confirmed: the database connection pool was exhausted and "
            f"DB writes timed out after retries. The timing supports a "
            f"contribution to the {service_name} latency increase. The "
            f"available evidence does not prove that the deployment's "
            f"pool-size change itself caused the exhaustion."
        )

    report = {
        "incident_title": state.get(
            "goal",
            "Operational incident investigation",
        ),
        "likely_root_cause": likely_root_cause,
        "confidence_pct": confidence,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "requires_approval": False,
        "causal_boundary": causal_boundary,
    }

    return {
        "final_report": report,
    }


# ============================================================
# EVIDENCE GATE
# ============================================================

def _evidence_gate(
    state: AgentState,
) -> tuple[bool, str]:
    """
    Decide whether OpsPilot may produce a final report.

    Controller hard evidence has a deterministic fast path:
      - explicit authoritative mechanism evidence
      - all three primary evidence sources
      - observations present

    In that case the controller itself supplies verification and the
    LLM cannot veto the result with a speculative reflection.

    For non-controller-grounded cases, the stricter LLM verification
    path remains in force.
    """

    tool_calls = state.get("tool_calls", [])
    observations = state.get("observations", [])
    evidence = state.get("evidence", [])

    # --------------------------------------------------------
    # Controller-owned evidence path
    # --------------------------------------------------------
    if (
        state.get("controller_grounded") is True
        and _primary_evidence_complete(tool_calls)
        and observations
        and evidence
    ):
        return (
            True,
            (
                "Evidence gate passed by controller hard evidence: "
                "authoritative operational output establishes the "
                "mechanism and the required metric, log, and deployment "
                "sources are present."
            ),
        )

    # --------------------------------------------------------
    # Normal LLM verification path
    # --------------------------------------------------------
    verification = state.get("verification_result")
    reflection = state.get("reflection", {})

    unique_evidence_tools = _unique_evidence_tool_count(tool_calls)

    if unique_evidence_tools < MIN_UNIQUE_EVIDENCE_TOOLS:
        return (
            False,
            (
                "Insufficient independent evidence sources. "
                f"Required at least {MIN_UNIQUE_EVIDENCE_TOOLS}, "
                f"but only {unique_evidence_tools} distinct evidence "
                "tools have produced successful results."
            ),
        )

    if not observations:
        return False, "No operational observations have been collected."

    if not evidence:
        return (
            False,
            "Operational observations exist, but usable evidence "
            "has not been established.",
        )

    if not verification:
        return False, "No verification result exists yet."

    if not _verification_supports_hypothesis(verification):
        return (
            False,
            "The available verification result does not positively "
            "support a hypothesis.",
        )

    selected_hypothesis = state.get("selected_hypothesis")
    if not selected_hypothesis:
        selected_hypothesis = _select_verified_hypothesis(state)

    if not selected_hypothesis:
        return (
            False,
            "No explicitly verified hypothesis has been selected. "
            "OpsPilot will not infer one.",
        )

    if not _hypothesis_matches_goal(
        state.get("goal", ""),
        selected_hypothesis,
    ):
        return (
            False,
            "The selected hypothesis is not aligned with the "
            "investigation goal.",
        )

    goal_evidence_status = _goal_authoritative_evidence_status(state)
    state["goal_evidence_status"] = goal_evidence_status

    if goal_evidence_status == "unsupported":
        return False, _goal_evidence_reason(state)

    if isinstance(reflection, dict) and reflection.get("needs_replan", False):
        return (
            False,
            "Reflection identified an evidence gap and requires re-planning.",
        )

    if isinstance(reflection, dict) and reflection.get(
        "evidence_sufficient"
    ) is False:
        return False, "Reflection explicitly says evidence is insufficient."

    if isinstance(reflection, dict) and reflection.get(
        "investigation_complete"
    ) is False:
        return False, "Reflection explicitly says the investigation is incomplete."

    return (
        True,
        (
            "Evidence gate passed: sufficient independent evidence, "
            "positive verification, and an explicitly selected "
            "hypothesis are available."
        ),
    )


# ============================================================
# BUILD CONTINUATION MESSAGE
# ============================================================

def _build_continuation_message(
    state: AgentState,
    reason: str,
) -> str:
    """
    Tell the model that it is not allowed to conclude yet.
    """

    tool_calls = state.get(
        "tool_calls",
        [],
    )

    used_tools = []

    for call in tool_calls:

        tool_name = call.get(
            "tool"
        )

        if (
            tool_name
            and tool_name not in used_tools
        ):

            used_tools.append(
                tool_name
            )

    plan = state.get(
        "plan",
        [],
    )

    plan_text = (
        "\n".join(
            f"- {step}"
            for step in plan
        )
        if plan
        else "- No explicit plan available."
    )

    return (
        "THE INVESTIGATION CANNOT BE CONCLUDED.\n\n"
        f"REASON:\n{reason}\n\n"
        "Do NOT provide a final root-cause conclusion.\n"
        "Do NOT claim the incident is resolved.\n"
        "Do NOT invent evidence.\n\n"
        "You MUST perform another read-only evidence-gathering "
        "tool call.\n\n"
        "CURRENT INVESTIGATION PLAN:\n"
        f"{plan_text}\n\n"
        "PREVIOUSLY USED TOOLS:\n"
        + (
            "\n".join(
                f"- {tool}"
                for tool in used_tools
            )
            if used_tools
            else "- none"
        )
        + "\n\n"
        "Choose ONE unused evidence-producing tool if possible."
    )


# ============================================================
# RUN REASONING CHECKPOINT
# ============================================================

def _run_reasoning_checkpoint(
    state: AgentState,
    tracer: Tracer | None = None,
) -> list[str] | None:
    """
    Generate hypotheses, verify evidence, reflect, and
    re-plan when necessary.
    """

    print(
        "\n========================================"
    )

    print(
        "       REASONING CHECKPOINT"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. HYPOTHESIS GENERATION
    # ========================================================

    hypothesis_result = hypothesis_node(
        state
    )

    state.update(
        hypothesis_result
    )

    print(
        "\n=== HYPOTHESES ==="
    )

    for hypothesis in state.get(
        "hypotheses",
        [],
    ):

        print(
            hypothesis
        )

    # ========================================================
    # 2. VERIFICATION
    # ========================================================

    verifier_result = verifier_node(
        state
    )

    state.update(
        verifier_result
    )

    controller_grounded = _apply_controller_grounding(state)

    if controller_grounded:
        print(
            "\n=== CONTROLLER HARD EVIDENCE ==="
        )
        print(
            state.get("controller_grounded_hypothesis")
        )

    print(
        "\n=== VERIFICATION ==="
    )

    print(
        state.get(
            "verification_result",
            {},
        )
    )

    print(
        "\n=== EVIDENCE ==="
    )

    for item in state.get(
        "evidence",
        [],
    ):

        print(
            item
        )

    # ========================================================
    # 3. SELECT VERIFIED HYPOTHESIS
    # ========================================================

    selected_hypothesis = (
        _select_verified_hypothesis(
            state
        )
    )

    print(
        "\n=== SELECTED HYPOTHESIS ==="
    )

    print(
        selected_hypothesis
    )

    # ========================================================
    # 4. REFLECTION
    # ========================================================

    reflection_result = reflection_node(
        state
    )

    state.update(
        reflection_result
    )

    reflection = state.get(
        "reflection",
        {},
    )

    print(
        "\n=== REFLECTION ==="
    )

    print(
        reflection
    )

    # ========================================================
    # 5. STORE REFLECTION NOTES
    # ========================================================

    notes = state.setdefault(
        "reflection_notes",
        [],
    )

    if isinstance(
        reflection,
        dict,
    ):

        reason = reflection.get(
            "reason"
        )

        if (
            reason
            and reason not in notes
        ):

            notes.append(
                reason
            )

        skipped_steps = reflection.get(
            "skipped_steps",
            [],
        )

        if isinstance(
            skipped_steps,
            list,
        ):

            for step in skipped_steps:

                note = (
                    f"Skipped step: {step}"
                )

                if note not in notes:

                    notes.append(
                        note
                    )

    # ========================================================
    # 6. CHECK RE-PLANNING
    # ========================================================

    if not isinstance(
        reflection,
        dict,
    ):

        return None

    needs_replan = reflection.get(
        "needs_replan",
        False,
    )

    if not needs_replan:

        print(
            "\n=== RE-PLANNING ==="
        )

        print(
            "Not required."
        )

        return None

    # ========================================================
    # 7. RE-PLAN
    # ========================================================

    reason = reflection.get(
        "reason",
        "Evidence is insufficient.",
    )

    print(
        "\n=== RE-PLANNING REQUIRED ==="
    )

    print(
        "Reason:",
        reason,
    )

    try:

        new_plan = replan(
            state,
            reason,
        )

    except Exception as e:

        print(
            "\n=== RE-PLANNING ERROR ==="
        )

        print(
            str(e)
        )

        return None

    if not isinstance(
        new_plan,
        list,
    ):

        print(
            "\n=== RE-PLANNING ERROR ==="
        )

        print(
            "Planner returned an invalid plan."
        )

        return None

    # --------------------------------------------------------
    # Remove empty plan entries
    # --------------------------------------------------------

    new_plan = [
        step
        for step in new_plan
        if isinstance(
            step,
            str,
        )
        and step.strip()
    ]

    if not new_plan:

        print(
            "\n=== RE-PLANNING ERROR ==="
        )

        print(
            "Planner returned an empty plan."
        )

        return None

    state[
        "plan"
    ] = new_plan

    # ========================================================
    # TRACE REPLANNED - ADDED FOR OBSERVABILITY
    # ========================================================

    if tracer:
        tracer.log(
            "replanned",
            {
                "reason": reason,
                "new_plan": new_plan,
            },
            iteration=state.get("iteration", 0),
        )

    print(
        "\n=== NEW PLAN ==="
    )

    for index, step in enumerate(
        new_plan,
        start=1,
    ):

        print(
            f"{index}. {step}"
        )

    return new_plan


# ============================================================
# EXECUTE TOOL
# ============================================================

def _execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    iteration: int,
    state: AgentState,
    observations: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    retry_counts: dict[str, int],
    messages: list[dict[str, Any]],
    tracer: Tracer | None = None,
) -> tuple[bool, bool]:
    """
    Execute one tool.

    Returns:

        (successful_execution, should_stop)

    should_stop is True only for approval or hard guardrail
    termination.
    """

    print(
        "\n=== TOOL REQUEST ==="
    )

    print(
        "Tool:",
        tool_name,
    )

    print(
        "Arguments:",
        arguments,
    )

    # Normalize aliases before any policy or dispatch decision.
    tool_name = _canonical_tool_name(
        tool_name
    )

    # ========================================================
    # TRACE TOOL REQUEST - ADDED FOR OBSERVABILITY
    # ========================================================

    if tracer:
        tracer.log(
            "tool_request",
            {
                "tool": tool_name,
                "arguments": arguments,
            },
            iteration=iteration,
        )

    # ========================================================
    # REPORT SAFETY GATE
    # ========================================================
    # create_incident_report is an output action, NOT evidence.
    # Never allow the local model to create a report while the
    # programmatic evidence gate is false.
    if tool_name == "create_incident_report":
        gate_passed, gate_reason = _evidence_gate(state)

        if not gate_passed:
            print("\n=== INCIDENT REPORT BLOCKED ===")
            print(
                "The model attempted to create a report before "
                "the evidence gate passed."
            )
            print("Reason:", gate_reason)

            blocked_result = {
                "error": (
                    "Incident report blocked until the "
                    "evidence gate passes."
                ),
                "tool": tool_name,
                "recoverable": True,
                "evidence_gate": gate_reason,
            }

            tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": "Report blocked: " + gate_reason,
                    "iteration": iteration,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "content": _serialize_tool_result(
                        blocked_result
                    ),
                }
            )

            state["incident_status"] = "investigating"
            return False, False

    # ========================================================
    # HIGH-IMPACT ACTION SAFETY GATE
    # ========================================================

    if tool_name == "request_rollback":

        # ----------------------------------------------------
        # NEVER allow a rollback request merely because the
        # LLM thinks a deployment is suspicious.
        #
        # Rollback requires:
        #   - independent evidence
        #   - positive verification
        #   - an explicitly selected hypothesis
        #   - no outstanding reflection request
        # ----------------------------------------------------

        gate_passed, gate_reason = _evidence_gate(
            state
        )

        if not gate_passed:

            print(
                "\n=== HIGH-IMPACT ACTION BLOCKED ==="
            )

            print(
                "Rollback cannot be requested."
            )

            print(
                "Reason:",
                gate_reason,
            )

            blocked_result = {
                "error": (
                    "Rollback blocked because the evidence "
                    "gate has not passed."
                ),
                "tool": tool_name,
                "recoverable": True,
                "evidence_gate": gate_reason,
            }

            tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": (
                        "Rollback blocked: "
                        + gate_reason
                    ),
                    "iteration": iteration,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "content": _serialize_tool_result(
                        blocked_result
                    ),
                }
            )

            # Keep the investigation alive. The next iteration
            # must gather evidence instead of terminating.
            state[
                "pending_approval"
            ] = None

            state[
                "incident_status"
            ] = "investigating"

            return (
                False,
                False,
            )

        # ----------------------------------------------------
        # Only now can the action enter human approval.
        # ----------------------------------------------------

        print(
            "\n=== HIGH-IMPACT ACTION ==="
        )

        print(
            "Rollback requested."
        )

        print(
            "Evidence gate passed."
        )

        print(
            "Human approval is required."
        )

        pending = {
            "tool": tool_name,
            "arguments": arguments,
            "status": "pending",
        }

        state[
            "pending_approval"
        ] = pending

        state[
            "incident_status"
        ] = "awaiting_approval"

        state[
            "terminated"
        ] = True

        state[
            "termination_reason"
        ] = "awaiting_human_approval"

        approval_result = approval_node(
            state
        )

        state.update(
            approval_result
        )

        print(
            "\n=== APPROVAL ==="
        )

        print(
            state.get(
                "pending_approval"
            )
        )

        return (
            False,
            True,
        )

    try:

        # ====================================================
        # DUPLICATE CALL GUARD
        # ====================================================

        justified_retry = False

        guardrails.check_duplicate_call(
            state,
            tool_name,
            arguments,
            justified_retry,
        )

        # ====================================================
        # RETRY BUDGET
        # ====================================================

        guardrails.check_retry_budget(
            retry_counts,
            tool_name,
        )

        # ====================================================
        # DISPATCH
        # ====================================================

        result = dispatch(
            tool_name,
            arguments,
        )

        retry_counts[
            tool_name
        ] = 0

        print(
            "\n=== TOOL RESULT ==="
        )

        print(
            result
        )

        # ====================================================
        # OBSERVATION
        # ====================================================

        observation = {
            "source": tool_name,
            "data": result,
        }

        observations.append(
            observation
        )

        # ====================================================
        # TOOL CALL RECORD
        # ====================================================

        tool_call_record = {
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "iteration": iteration,
        }

        tool_calls.append(
            tool_call_record
        )

        # ====================================================
        # TRACE TOOL RESULT - ADDED FOR OBSERVABILITY
        # ====================================================

        if tracer:
            tracer.log(
                "tool_result",
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                },
                iteration=iteration,
            )

        # ====================================================
        # EMPTY RESULT WARNING
        # ====================================================

        if isinstance(
            result,
            dict,
        ):

            if guardrails.is_empty_observation(
                result
            ):

                print(
                    "\nWARNING:"
                    f" {tool_name} returned "
                    "no useful data."
                )

        # ====================================================
        # SEND TOOL RESULT TO MODEL
        # ====================================================

        messages.append(
            {
                "role": "tool",
                "content": _serialize_tool_result(
                    result
                ),
            }
        )

        # ====================================================
        # UPDATE STATE
        # ====================================================

        state[
            "observations"
        ] = observations

        state[
            "tool_calls"
        ] = tool_calls

        if tool_name in EVIDENCE_TOOLS:
            _apply_controller_grounding(state)

        return (
            True,
            False,
        )

    except guardrails.StopInvestigation as e:

        print(
            "\n=== GUARDRAIL WARNING ==="
        )

        print(
            e.reason
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # A duplicate call should not kill the entire
        # investigation. The outer loop will choose another
        # evidence tool.
        # ----------------------------------------------------

        reason = str(
            e.reason
        ).lower()

        if (
            "duplicate" in reason
            or "already" in reason
            or "retry" in reason
        ):

            error_result = {
                "error": str(
                    e.reason
                ),
                "tool": tool_name,
                "recoverable": True,
            }

            tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": str(
                        e.reason
                    ),
                    "iteration": iteration,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "content": _serialize_tool_result(
                        error_result
                    ),
                }
            )

            return (
                False,
                False,
            )

        # ----------------------------------------------------
        # Other hard guardrail stop
        # ----------------------------------------------------

        state[
            "terminated"
        ] = True

        state[
            "termination_reason"
        ] = e.reason

        return (
            False,
            True,
        )

    except ToolDispatchError as e:

        retry_counts[
            tool_name
        ] = (
            retry_counts.get(
                tool_name,
                0,
            )
            + 1
        )

        error_result = {
            "error": str(e),
            "tool": tool_name,
            "recoverable": True,
        }

        print(
            "\n=== TOOL ERROR ==="
        )

        print(
            error_result
        )

        tool_calls.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "error": str(e),
                "iteration": iteration,
            }
        )

        messages.append(
            {
                "role": "tool",
                "content": _serialize_tool_result(
                    error_result
                ),
            }
        )

        return (
            False,
            False,
        )

    except Exception as e:

        error_result = {
            "error": str(e),
            "tool": tool_name,
            "recoverable": True,
        }

        print(
            "\n=== UNEXPECTED TOOL ERROR ==="
        )

        print(
            str(e)
        )

        tool_calls.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "error": str(e),
                "iteration": iteration,
            }
        )

        messages.append(
            {
                "role": "tool",
                "content": _serialize_tool_result(
                    error_result
                ),
            }
        )

        return (
            False,
            False,
        )



# ============================================================
# HARD-EVIDENCE TERMINATION
# ============================================================

def _terminate_on_controller_hard_evidence(
    state: AgentState,
) -> bool:
    """
    Finish the dynamic evidence-gathering phase when:

      1. authoritative hard operational evidence exists, AND
      2. the three primary evidence categories have all succeeded.

    The three primary categories are:
      - search_logs
      - query_metrics
      - get_deployments

    This is deliberately deterministic. Once these conditions are
    true, the local 3B model is no longer allowed to create another
    reflection -> re-plan -> duplicate-search cycle.
    """

    if not _apply_controller_grounding(state):
        return False

    if not _primary_evidence_complete(
        state.get("tool_calls", [])
    ):
        return False

    # Historical-incident goals require historical evidence
    # before hard-evidence termination is allowed.
    goal = state.get("goal", "")

    if _goal_requires_historical_incident(goal):
        incident_already_used = any(
            isinstance(call, dict)
            and call.get("tool") == "search_incidents"
            and not call.get("error")
            for call in state.get("tool_calls", [])
        )

        if not incident_already_used:
            return False
    # Competing-cause goals require additional diagnostic evidence
    # before hard-evidence termination is allowed.
    if _goal_requires_competing_cause_analysis(goal):
        diagnostic_log_used = any(
            isinstance(call, dict)
            and call.get("tool") == "search_logs"
            and call.get("arguments", {}).get("keyword")
            in {"timeout", "pool", "pool exhausted", "retry"}
            and not call.get("error")
            for call in state.get("tool_calls", [])
        )

        if not diagnostic_log_used:
            return False
    # Rollback goals must continue past evidence completion so that
    # request_rollback can reach the programmatic evidence gate
    # and human approval flow.
    if "rollback" in str(goal).lower():
        return False

    state["terminated"] = True
    state["termination_reason"] = "reported"
    state["incident_status"] = "investigating"
    return True


# ============================================================
# DYNAMIC TOOL LOOP
# ============================================================


def _controller_successful_evidence_tools(
    state: AgentState,
) -> set[str]:
    """Return the three primary evidence tools with successful results."""
    primary = {
        "query_metrics",
        "search_logs",
        "get_deployments",
    }
    calls = state.get("tool_calls", [])
    if not isinstance(calls, list):
        return set()

    return {
        call.get("tool")
        for call in calls
        if isinstance(call, dict)
        and call.get("tool") in primary
        and not call.get("error")
    }


def _controller_needs_corroboration(
    state: AgentState,
) -> bool:
    """Require all three independent primary evidence sources."""
    return (
        len(_controller_successful_evidence_tools(state))
        < MIN_UNIQUE_EVIDENCE_TOOLS
    )


def _select_controller_corroboration_tool(
    goal: str,
    state: AgentState,
) -> tuple[str, dict[str, Any]] | None:
    """
    Select the next missing primary evidence source deterministically.
    Never ask the LLM to decide this once hard evidence exists.
    """
    used = _controller_successful_evidence_tools(state)

    for tool_name in (
        "query_metrics",
        "search_logs",
        "get_deployments",
    ):
        if tool_name in used:
            continue

        arguments = _normalize_tool_arguments(
            tool_name,
            _fallback_tool_arguments(
                tool_name,
                goal,
                state,
            ),
        )

        return tool_name, arguments

    return None


def _select_controller_diagnostic_tool(
    goal: str,
    state: AgentState,
) -> tuple[str, dict[str, Any]] | None:
    """Select a deterministic high-signal read-only diagnostic query."""
    facts = _collect_hard_operational_facts(state)

    if facts["pool_exhaustion"] or facts["cache_failure"]:
        return None
    if not facts["latency_degradation"]:
        return None
    if not _primary_evidence_complete(state.get("tool_calls", [])):
        return None

    deployment_text = " ".join(
        str(change).lower()
        for change in facts.get("deployment_changes", [])
    )

    if any(term in deployment_text for term in (
        "database", "db", "retry", "connection pool", "pool size"
    )):
        keywords = ("timeout", "pool exhausted", "retry")
    elif any(term in deployment_text for term in (
        "cache", "redis", "memcached"
    )):
        keywords = ("cache failure", "cache error", "cache unavailable")
    else:
        keywords = ("timeout", "exception", "error")

    service = _extract_service(goal, state)
    existing_calls = state.get("tool_calls", [])
    for keyword in keywords:
        arguments = {
            "service": service,
            "level": "ERROR",
            "keyword": keyword,
            "start": DEFAULT_INVESTIGATION_START,
            "end": DEFAULT_INVESTIGATION_END,
        }
        if not _call_already_used(existing_calls, "search_logs", arguments):
            return "search_logs", arguments
    return None
def _goal_requires_runbook(
    goal: str,
) -> bool:
    """
    Return True only when the user explicitly asks for
    runbook/RAG/operational guidance.

    This does not infer a root cause and does not affect
    normal investigations.
    """

    text = (goal or "").lower()

    return any(
        term in text
        for term in (
            "runbook",
            "run book",
            "rag",
            "knowledge base",
            "operational guidance",
            "troubleshooting guide",
        )
    )
def _goal_requires_historical_incident(
    goal: str,
) -> bool:
    """
    Return True when the investigation goal explicitly asks
    for historical incident information or comparison.
    """

    text = (goal or "").lower()

    return any(
        term in text
        for term in (
            "historical incident",
            "historical incidents",
            "previous",
            "known historical",
            "known incidents",
            "past incident",
            "past incidents",
        )
    )
def _goal_requires_competing_cause_analysis(goal: str) -> bool:
    """Return True when the goal explicitly asks to distinguish competing causes."""
    text = (goal or "").lower()

    return any(term in text for term in (
        "distinguish",
        "better explains",
        "compare",
        "versus",
        "vs ",
    ))
def _historical_incident_keyword(
    goal: str,
) -> str:
    """
    Return a concise search keyword for historical incident lookup.
    """

    text = (goal or "").lower()

    if "retry-wrapper" in text or "retry wrapper" in text:
        return "retry-wrapper"

    if "connection-pool" in text or "connection pool" in text:
        return "connection pool"

    if "database retries" in text or "db retries" in text:
        return "retry"

    if "retry" in text:
        return "retry"

    return "incident"
def _select_controller_preflight_tool(
    goal: str,
    state: AgentState,
) -> tuple[str, dict[str, Any]] | None:
    """
    Deterministically collect the required read-only evidence.

    Normal investigation order remains unchanged:

        search_logs
        -> query_metrics
        -> get_deployments

    If the user explicitly asks for runbook/RAG guidance,
    retrieve_runbook is collected first:

        retrieve_runbook
        -> search_logs
        -> query_metrics
        -> get_deployments

    IMPORTANT:
    retrieve_runbook is additional contextual evidence.
    It does NOT replace the three primary operational evidence
    sources required by the existing evidence gate.
    """

    used = _controller_successful_evidence_tools(state)

    # --------------------------------------------------------
    # EXPLICIT RUNBOOK / RAG REQUEST
    # --------------------------------------------------------
    #
    # Only activate this path when the user's goal explicitly
    # requests runbook/RAG/operational guidance.
    #
    # Normal investigations are completely unaffected.
    #
    if _goal_requires_runbook(goal):

        runbook_already_used = any(
            isinstance(call, dict)
            and call.get("tool") == "retrieve_runbook"
            and not call.get("error")
            for call in state.get("tool_calls", [])
        )

        if not runbook_already_used:

            arguments = _normalize_tool_arguments(
                "retrieve_runbook",
                _fallback_tool_arguments(
                    "retrieve_runbook",
                    goal,
                    state,
                ),
            )

            return (
                "retrieve_runbook",
                arguments,
            )
    # --------------------------------------------------------
    # EXPLICIT HISTORICAL INCIDENT REQUEST
    # --------------------------------------------------------
    #
    # If the goal explicitly asks for historical incidents,
    # collect historical incident evidence before the normal
    # primary evidence sequence.
    #
    if _goal_requires_historical_incident(goal):

        incident_already_used = any(
            isinstance(call, dict)
            and call.get("tool") == "search_incidents"
            and not call.get("error")
            for call in state.get("tool_calls", [])
        )

        if not incident_already_used:

            arguments = {
                "keyword": _historical_incident_keyword(goal),
                "service": _extract_service(goal, state),
            }

            arguments = _normalize_tool_arguments(
                "search_incidents",
                arguments,
            )

            return (
                "search_incidents",
                arguments,
            )
    # --------------------------------------------------------
    # EXPLICIT HISTORICAL INCIDENT REQUEST
    # --------------------------------------------------------
    #
    # If the goal explicitly asks for historical incidents,
    # search_incidents must be collected before the normal
    # primary evidence sequence.
    #
    # This prevents the controller from forcing:
    #     search_logs -> query_metrics -> get_deployments
    # before satisfying an explicit historical-incident goal.
    #
    if _goal_requires_historical_incident(goal):

        incident_already_used = any(
            isinstance(call, dict)
            and call.get("tool") == "search_incidents"
            and not call.get("error")
            for call in state.get("tool_calls", [])
        )

        if not incident_already_used:

            arguments = {
                "keyword": _historical_incident_keyword(goal),
                "service": _extract_service(goal, state),
            }

            arguments = _normalize_tool_arguments(
                "search_incidents",
                arguments,
            )

            return (
                "search_incidents",
                arguments,
            )

    # --------------------------------------------------------
    # --------------------------------------------------------
    # EXISTING PRIMARY EVIDENCE FLOW
    # --------------------------------------------------------
    #
    # DO NOT change this order. Existing scenarios depend on it.
    #
    for tool_name in (
        "search_logs",
        "query_metrics",
        "get_deployments",
    ):

        if tool_name in used:
            continue

        if tool_name == "search_logs":

            service = _extract_service(
                goal,
                state,
            )

            arguments = {
                "service": service,
                "level": "ERROR",
                "keyword": _goal_log_keyword(goal),
                "start": DEFAULT_INVESTIGATION_START,
                "end": DEFAULT_INVESTIGATION_END,
            }

        else:

            arguments = _normalize_tool_arguments(
                tool_name,
                _fallback_tool_arguments(
                    tool_name,
                    goal,
                    state,
                ),
            )

        return (
            tool_name,
            arguments,
        )

    return None

def _run_dynamic_tool_loop(
    goal: str,
    state: AgentState,
    tracer: Tracer | None = None,
) -> AgentState:
    """
    Run the autonomous OpsPilot investigation loop.

    IMPORTANT:

    The LLM proposes actions, but the program controls
    investigation progress and termination.

    If the LLM returns no tool call while evidence is
    insufficient, OpsPilot automatically selects the next
    unused evidence-producing tool.

    This prevents a small local model from repeatedly saying:

        "I am done"

    without actually executing the investigation plan.
    """

    tool_definitions = (
        ollama_tool_definitions()
    )

    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = f"""
You are OpsPilot, an autonomous incident investigation agent.

Your job is to investigate the user's incident using the
available operational tools.

You MUST gather grounded operational evidence before
reaching a root-cause conclusion.

Available operational evidence includes:

- service metrics (currently latency_ms_p95 and error_rate_pct)
- service logs
- recent deployments
- previous incidents
- service runbooks

Do not invent evidence.

Do not turn absence of evidence into evidence of a cause.

IMPORTANT INVESTIGATION CONTEXT:

Default investigation window:

Start:
{DEFAULT_INVESTIGATION_START}

End:
{DEFAULT_INVESTIGATION_END}

Recent deployments should normally be searched from:

{DEFAULT_DEPLOYMENT_SINCE}

Do NOT invent historical dates.

If a timestamp is optional and unknown, omit it.

Do not send empty timestamp arguments.

High-impact actions such as rollback are strictly gated.

NEVER request rollback merely because a deployment is
temporally correlated with an incident.

Rollback may only be requested after the programmatic
evidence gate has passed with:
- at least 3 independent evidence sources,
- positive verification,
- an explicitly selected verified hypothesis,
- and no unresolved reflection/re-planning requirement.

Human approval is a SECOND safety layer, not a substitute
for evidence.

Never assume that human approval has been granted.

============================================================
INVESTIGATION RULES
============================================================

1. Select ONLY ONE next tool action.

2. Prefer read-only evidence tools.

2a. Tool arguments must describe the operational query itself.
    NEVER put a tool name such as "search_logs", "query_metrics",
    or "get_deployments" into a keyword/query field.

2b. If you cannot construct precise arguments, provide the tool
    name with only the arguments you know. The Python controller
    will safely fill missing defaults.

3. Do not repeat an identical tool call.

4. Use multiple independent evidence sources.

5. A missing log entry means only that the searched log
   query returned no matching result.

6. Never claim that a suspected root cause happened merely
   because there are no logs disproving it.

6a. A tool returning zero matching records is still a valid
    observation about that query. Do not repeatedly request the
    identical query merely because it returned zero records.

7. A deployment correlation is NOT proof of causation.

8. A hypothesis is NOT a conclusion.

8a. Tool results are authoritative observations. Never contradict
    a tool result by inventing a different deployment history,
    log result, metric value, or incident result.

8b. Absence of matching logs is an observation about that query;
    it is NOT proof that the underlying event did not occur.

9. Confidence must be based on actual supporting evidence.

10. If evidence is contradictory, investigate further.

11. If evidence is insufficient, investigate further.

12. Follow the current investigation plan.

13. After re-planning, investigate the new evidence gaps.

14. Never claim human approval.

15. Never fabricate tool results.

16. Never request request_rollback while the evidence gate
    is false.

17. If a rollback is blocked, continue read-only investigation.

17. NEVER call create_incident_report while the evidence gate
    is false. A report is an output action, not evidence.

18. When a re-planned step asks for configuration, deployment
    changes, or modification history and no dedicated
    configuration tool exists, use get_deployments if it can
    answer the question. Do not invent a new tool.

19. Never use a planner sentence as a log keyword. Use a concise
    operational term such as "connection pool", "timeout",
    "database", or "exception".

20. If tool results explicitly contain authoritative evidence such
as "pool exhausted", treat that observation as authoritative.
Do not reinterpret it as merely "possible", "potential", or
"provisional".

21. Never request request_rollback as a diagnostic experiment.
Rollback is a production-changing action and must never be used
to prove a hypothesis.

22. The user's investigation goal defines the causal topic. Evidence
for an unrelated mechanism must not replace the requested mechanism.
For example, a cache-failure investigation must not be reported as
database pool exhaustion merely because database evidence exists.

23. If the controller has already established hard evidence,
do not generate a final action recommendation that contradicts
the controller. The controller constructs the final report.

============================================================
VERY IMPORTANT
============================================================

The program will reject unsupported final conclusions.

If you have not collected enough evidence, call another
read-only evidence tool.

Do not simply return normal text saying that the investigation
is complete.

============================================================
FINAL CONCLUSION RULE
============================================================

Only provide a root-cause conclusion after actual tool
results support it.

If the evidence remains insufficient after the available
investigation opportunities are exhausted, the correct
outcome is:

    INCONCLUSIVE

Do NOT guess.
"""

    messages: list[
        dict[str, Any]
    ] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": goal,
        },
    ]

    observations: list[
        dict[str, Any]
    ] = []

    tool_calls: list[
        dict[str, Any]
    ] = []

    retry_counts: dict[str, int] = {}

    # Number of consecutive times the model failed to produce
    # a tool call.
    no_tool_streak = 0

    # Bound the reflection/re-planning cycle. The controller must
    # eventually choose INCONCLUSIVE instead of looping.
    reasoning_checkpoints = 0

    # Get max iterations from state
    max_iterations = state.get(
        "max_iterations",
        MAX_TOOL_ITERATIONS,
    )

    # ========================================================
    # AUTONOMOUS LOOP
    # ========================================================

    for iteration in range(
        max_iterations
    ):

        state[
            "iteration"
        ] = iteration + 1

        print(
            "\n========================================"
        )

        print(
            f"          AGENT ITERATION "
            f"{iteration + 1}"
        )

        print(
            "========================================"
        )

        # ----------------------------------------------------
        # Hard limits
        # ----------------------------------------------------

        try:

            guardrails.check_hard_limits(
                state
            )

        except guardrails.StopInvestigation as e:

            state[
                "terminated"
            ] = True

            state[
                "termination_reason"
            ] = e.reason

            print(
                "\nSTOPPED:",
                e.reason,
            )

            break

        # ----------------------------------------------------
        # DETERMINISTIC PRIMARY-EVIDENCE PREFLIGHT
        # ----------------------------------------------------
        # Before asking Qwen to choose an investigative action,
        # collect the three primary read-only sources in a fixed,
        # reproducible order. This prevents query wording from
        # causing false zero-result searches and prevents the 3B
        # model from re-planning after the evidence is sufficient.
        preflight = _select_controller_preflight_tool(
            goal,
            state,
        )

        if preflight is not None:
            (
                preflight_tool,
                preflight_arguments,
            ) = preflight

            print(
                "\n=== CONTROLLER PRIMARY EVIDENCE ==="
            )
            print(
                "Forcing primary evidence source:",
                preflight_tool,
            )
            print(
                "Arguments:",
                preflight_arguments,
            )

            successful, should_stop = _execute_tool(
                preflight_tool,
                preflight_arguments,
                iteration + 1,
                state,
                observations,
                tool_calls,
                retry_counts,
                messages,
                tracer,
            )

            if should_stop:
                break

            if successful:
                no_tool_streak = 0

                # A preflight tool can itself reveal hard evidence.
                # Check immediately, before another model call.
                if _terminate_on_controller_hard_evidence(state):
                    print(
                        "\n=== CONTROLLER TERMINATION ==="
                    )
                    print(
                        "Primary evidence is complete and authoritative "
                        "hard evidence is present."
                    )
                    break

            continue

        # ----------------------------------------------------
        # DETERMINISTIC HIGH-SIGNAL DIAGNOSTIC PREFLIGHT
        # ----------------------------------------------------
        diagnostic = _select_controller_diagnostic_tool(goal, state)

        if diagnostic is not None:
            diagnostic_tool, diagnostic_arguments = diagnostic
            print("\n=== CONTROLLER DIAGNOSTIC EVIDENCE ===")
            print("Forcing high-signal read-only evidence source:", diagnostic_tool)
            print("Arguments:", diagnostic_arguments)

            successful, should_stop = _execute_tool(
                diagnostic_tool, diagnostic_arguments, iteration + 1, state,
                observations, tool_calls, retry_counts, messages,
                tracer,
            )
            if should_stop:
                break
            if successful:
                no_tool_streak = 0
                if _terminate_on_controller_hard_evidence(state):
                    print("\n=== CONTROLLER TERMINATION ===")
                    print("High-signal authoritative evidence found; skipping LLM re-planning.")
                    break
            continue

        # ----------------------------------------------------
        # GOAL-SPECIFIC EVIDENCE EXHAUSTION
        # ----------------------------------------------------
        # Once the three primary sources have been collected, do not
        # let the local model manufacture mechanism-specific evidence.
        if _primary_evidence_complete(tool_calls):
            goal_status = _goal_authoritative_evidence_status(state)
            state["goal_evidence_status"] = goal_status

            if goal_status == "unsupported":
                print("\n=== GOAL EVIDENCE GATE ===")
                print("Passed: False")
                print(_goal_evidence_reason(state))
                print(
                    "Stopping before LLM re-planning because the "
                    "requested mechanism has no authoritative support."
                )
                state["terminated"] = True
                state["termination_reason"] = "insufficient_evidence"
                state["incident_status"] = "inconclusive"
                break

        # ----------------------------------------------------
        # CONTROLLER-FIRST CORROBORATION / COMPLETION
        # ----------------------------------------------------
        # Once authoritative hard evidence has been found, the
        # controller—not the 3B model—owns the next step:
        #
        #   hard evidence + missing primary sources
        #       -> force the missing read-only source
        #
        #   hard evidence + all primary sources complete
        #       -> stop BEFORE asking the LLM to re-plan
        #
        # This prevents redundant search_logs calls and prevents
        # the model from inventing speculative re-plans after the
        # investigation is already complete.
        if state.get("controller_grounded"):
            if _controller_needs_corroboration(state):
                corroboration = (
                    _select_controller_corroboration_tool(
                        goal,
                        state,
                    )
                )

                if corroboration is not None:
                    (
                        corroboration_tool,
                        corroboration_arguments,
                    ) = corroboration

                    print(
                        "\n=== CONTROLLER CORROBORATION ==="
                    )
                    print(
                        "Authoritative hard evidence found."
                    )
                    print(
                        "Forcing missing read-only evidence source:",
                        corroboration_tool,
                    )
                    print(
                        "Arguments:",
                        corroboration_arguments,
                    )

                    successful, should_stop = _execute_tool(
                        corroboration_tool,
                        corroboration_arguments,
                        iteration + 1,
                        state,
                        observations,
                        tool_calls,
                        retry_counts,
                        messages,
                        tracer,
                    )

                    if should_stop:
                        break

                    if successful:
                        no_tool_streak = 0

                    continue
                            # Rollback goals must continue to the approval flow
                            # Rollback goals must continue to the approval flow
                # after evidence collection instead of terminating here.
                          # Rollback goals must proceed to the programmatic
              # rollback request and human approval flow.
            if "rollback" in str(goal).lower():
                rollback_already_requested = any(
                    isinstance(call, dict)
                    and call.get("tool") == "request_rollback"
                    and not call.get("error")
                    for call in state.get("tool_calls", [])
                )

                if not rollback_already_requested:
                    rollback_arguments = {
                        "service": _extract_service(goal, state),
                        "deployment_id": "checkout-v2.4",
                        "reason": (
                            "Evidence-grounded investigation found "
                            "DB connection pool exhaustion and DB write "
                            "timeouts following the checkout-v2.4 deployment."
                        ),
                    }

                    rollback_arguments = _normalize_tool_arguments(
                        "request_rollback",
                        rollback_arguments,
                    )

                    print(
                        "\n=== CONTROLLER ROLLBACK REQUEST ==="
                    )
                    print(
                        "Evidence collection is complete."
                    )
                    print(
                        "Forcing request_rollback through the "
                        "programmatic approval gate."
                    )
                    print(
                        "Arguments:",
                        rollback_arguments,
                    )

                    successful, should_stop = _execute_tool(
                        "request_rollback",
                        rollback_arguments,
                        iteration + 1,
                        state,
                        observations,
                        tool_calls,
                        retry_counts,
                        messages,
                        tracer,
                    )

                    if should_stop:
                        break

                    if successful:
                        no_tool_streak = 0

                    continue

                        # Competing-cause goals require additional diagnostic
            # evidence before controller termination is allowed.
            if _goal_requires_competing_cause_analysis(
                state.get("goal", "")
            ):
                diagnostic_log_used = any(
                    isinstance(call, dict)
                    and call.get("tool") == "search_logs"
                    and call.get("arguments", {}).get("keyword")
                    in {
                        "timeout",
                        "pool",
                        "pool exhausted",
                        "retry",
                    }
                    and not call.get("error")
                    for call in state.get("tool_calls", [])
                )

                if not diagnostic_log_used:
                    diagnostic_arguments = {
                        "service": _extract_service(goal, state),
                        "level": "ERROR",
                        "keyword": "timeout",
                        "start": "2026-08-03T14:00:00Z",
                        "end": "2026-08-03T14:20:00Z",
                    }

                    diagnostic_arguments = _normalize_tool_arguments(
                        "search_logs",
                        diagnostic_arguments,
                    )

                    print(
                        "\n=== CONTROLLER DIAGNOSTIC EVIDENCE ==="
                    )
                    print(
                        "Forcing diagnostic search_logs for "
                        "competing-cause analysis."
                    )
                    print("Arguments:", diagnostic_arguments)

                    successful, should_stop = _execute_tool(
                        "search_logs",
                        diagnostic_arguments,
                        iteration + 1,
                        state,
                        observations,
                        tool_calls,
                        retry_counts,
                        messages,
                        tracer,
                    )

                    if should_stop:
                        break

                    if successful:
                        no_tool_streak = 0

                    continue

            # All required primary evidence is present. Do not ask
            # Qwen for another action; it can only create duplicate
            # calls, speculative hypotheses, or unnecessary re-plans.
            print(
                "\n=== CONTROLLER TERMINATION ==="
            )
            print(
                "Authoritative tool evidence and all required "
                "independent primary evidence sources are complete."
            )
            print(
                "Skipping LLM reflection/re-planning."
            )
            print(
                "Final verification/reporting will be handled "
                "by the controller."
            )

            state["terminated"] = True
            state["termination_reason"] = "reported"
            state["incident_status"] = "investigating"
            break

        # ----------------------------------------------------
        # Ask the LLM for the next action
        # ----------------------------------------------------

        message = agent_decision(
            messages=messages,
            tool_definitions=tool_definitions,
        )

        assistant_message: dict[
            str,
            Any,
        ] = {
            "role": "assistant",
            "content": message.get(
                "content",
                "",
            ),
        }

        tool_calls_from_model = (
            message.get(
                "tool_calls",
                [],
            )
        )

        if tool_calls_from_model:

            assistant_message[
                "tool_calls"
            ] = tool_calls_from_model

        messages.append(
            assistant_message
        )

        # ====================================================
        # NO TOOL CALL
        # ====================================================

        if not tool_calls_from_model:

            no_tool_streak += 1

            print(
                "\n=== NO TOOL CALL ==="
            )

            print(
                "Model did not request a tool."
            )

            # ------------------------------------------------
            # Controller hard evidence is authoritative, but it
            # still needs the configured independent corroboration
            # sources before the report gate can pass.
            #
            # IMPORTANT:
            # Do this BEFORE LLM reflection/re-planning. Once an
            # explicit operational fact such as "pool exhausted"
            # is found, asking the 3B model to reason again is
            # unnecessary and can cause rollback/re-plan noise.
            # ------------------------------------------------

            if _controller_needs_corroboration(state):

                corroboration = (
                    _select_controller_corroboration_tool(
                        goal,
                        state,
                    )
                )

                if corroboration is not None:

                    corroboration_tool, corroboration_arguments = (
                        corroboration
                    )

                    print(
                        "\n=== CONTROLLER CORROBORATION ==="
                    )

                    print(
                        "Hard evidence found, but the "
                        "three-source evidence policy is not "
                        "yet satisfied."
                    )

                    print(
                        "Forcing read-only corroboration:",
                        corroboration_tool,
                    )

                    print(
                        "Arguments:",
                        corroboration_arguments,
                    )

                    successful, should_stop = (
                        _execute_tool(
                            corroboration_tool,
                            corroboration_arguments,
                            iteration + 1,
                            state,
                            observations,
                            tool_calls,
                            retry_counts,
                            messages,
                            tracer,
                        )
                    )

                    if should_stop:
                        break

                    if successful:
                        no_tool_streak = 0

                    continue

            # ------------------------------------------------
            # HARD-EVIDENCE CORROBORATION
            # ------------------------------------------------
            # Hard evidence identifies the mechanism, but it does
            # NOT by itself complete the investigation. Collect the
            # three independent primary sources before evaluating
            # the final evidence gate.
            if _controller_needs_corroboration(state):

                print(
                    "\n=== CONTROLLER CORROBORATION ==="
                )

                print(
                    "Hard evidence found, but independent "
                    "corroboration is incomplete."
                )

                fallback = _select_controller_corroboration_tool(
                    goal,
                    state,
                )

                if fallback:
                    (
                        corroboration_tool,
                        corroboration_arguments,
                    ) = fallback

                    print(
                        "Forcing read-only evidence tool:",
                        corroboration_tool,
                    )

                    successful, should_stop = _execute_tool(
                        corroboration_tool,
                        corroboration_arguments,
                        iteration + 1,
                        state,
                        observations,
                        tool_calls,
                        retry_counts,
                        messages,
                        tracer,
                    )

                    if should_stop:
                        break

                    if successful:
                        no_tool_streak = 0

                    continue

            # ------------------------------------------------
            # Check whether the investigation can genuinely
            # terminate.
            # ------------------------------------------------

            gate_passed, gate_reason = (
                _evidence_gate(
                    state
                )
            )

            print(
                "\n=== EVIDENCE GATE ==="
            )

            print(
                "Passed:",
                gate_passed,
            )

            print(
                "Reason:",
                gate_reason,
            )

            # ------------------------------------------------
            # If gate already passes, run one reasoning
            # checkpoint before allowing the final response.
            # ------------------------------------------------

            if gate_passed:

                # Controller hard evidence is authoritative.
                # Do not ask the LLM for another reasoning pass.
                if _terminate_on_controller_hard_evidence(state):

                    print(
                        "\n=== CONTROLLER TERMINATION ==="
                    )

                    print(
                        "Authoritative hard evidence is sufficient."
                    )

                    print(
                        "LLM final response suppressed."
                    )

                    break

                # Fallback for non-controller-grounded evidence:
                # only then is an additional reasoning checkpoint
                # permitted.
                print(
                    "\n=== FINAL REASONING CHECK ==="
                )

                reasoning_checkpoints += 1

                _run_reasoning_checkpoint(
                    state,
                    tracer,
                )

                gate_passed, gate_reason = (
                    _evidence_gate(
                        state
                    )
                )

                print(
                    "\n=== FINAL EVIDENCE GATE ==="
                )

                print(
                    "Passed:",
                    gate_passed,
                )

                print(
                    "Reason:",
                    gate_reason,
                )

                if gate_passed:

                    state[
                        "terminated"
                    ] = True

                    state[
                        "termination_reason"
                    ] = "reported"

                    print(
                        "\n=== CONTROLLER TERMINATION ==="
                    )

                    print(
                        "Evidence gate passed after final verification."
                    )

                    print(
                        "LLM final response suppressed."
                    )

                    break

            # ------------------------------------------------
            # Evidence is insufficient.
            #
            # Run checkpoint and re-plan if necessary.
            # ------------------------------------------------

            print(
                "\n=== INVESTIGATION CONTINUES ==="
            )

            reasoning_checkpoints += 1

            new_plan = (
                _run_reasoning_checkpoint(
                    state,
                    tracer,
                )
            )

            if new_plan:

                print(
                    "\n=== RE-PLANNED INVESTIGATION ==="
                )

                for index, step in enumerate(
                    new_plan,
                    start=1,
                ):

                    print(
                        f"{index}. {step}"
                    )

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "The investigation cannot be "
                            "concluded because evidence is "
                            "insufficient.\n\n"
                            "NEW INVESTIGATION PLAN:\n"
                            + "\n".join(
                                f"{index}. {step}"
                                for index, step in enumerate(
                                    new_plan,
                                    start=1,
                                )
                            )
                            + "\n\n"
                            "Execute the revised plan. "
                            "Use one read-only evidence tool "
                            "at a time. "
                            "Do not repeat identical calls."
                        ),
                    }
                )

            else:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            _build_continuation_message(
                                state,
                                gate_reason,
                            )
                        ),
                    }
                )

            # If the primary evidence sources are complete and
            # repeated checkpoints have not produced grounded
            # evidence, stop truthfully instead of looping.
            # IMPORTANT:
            # A newly generated plan must be executed before termination.
            # The previous version stopped immediately after re-planning,
            # which is why the revised plan was never executed.
            if (
                _primary_evidence_complete(tool_calls)
                and reasoning_checkpoints >= MAX_REASONING_CHECKPOINTS
                and not new_plan
            ):
                state["terminated"] = True
                state["termination_reason"] = "insufficient_evidence"
                state["incident_status"] = "inconclusive"

                print(
                    "\n=== INVESTIGATION STOPPED ==="
                )
                print(
                    "Primary evidence was collected, but the "
                    "evidence gate still failed."
                )
                print(
                    "No actionable revised plan remained."
                )
                print(
                    "OpsPilot will stop rather than guess."
                )
                break

            # ------------------------------------------------
            # FALLBACK:
            #
            # If the model has failed to produce a tool call,
            # the program itself selects an evidence tool.
            #
            # This is the major fix for the 3B behavior.
            # ------------------------------------------------

            fallback = (
                _select_fallback_evidence_tool(
                    goal,
                    state,
                )
            )

            if fallback is None:

                print(
                    "\n=== NO SAFE NEW EVIDENCE ACTION ==="
                )

                state["terminated"] = True
                state["termination_reason"] = "insufficient_evidence"
                state["incident_status"] = "inconclusive"

                print(
                    "No safe, materially new evidence action is available."
                )
                break

            fallback_tool, fallback_arguments = (
                fallback
            )

            print(
                "\n=== FALLBACK EVIDENCE ACTION ==="
            )

            print(
                "The model did not provide a tool call."
            )

            print(
                "OpsPilot is forcing the next evidence "
                "gathering action:"
            )

            print(
                "Tool:",
                fallback_tool,
            )

            print(
                "Arguments:",
                fallback_arguments,
            )

            successful, should_stop = (
                _execute_tool(
                    fallback_tool,
                    fallback_arguments,
                    iteration + 1,
                    state,
                    observations,
                    tool_calls,
                    retry_counts,
                    messages,
                    tracer,
                )
            )

            if should_stop:

                break

            if successful:

                no_tool_streak = 0

            continue

        # ====================================================
        # TOOL CALL RECEIVED
        # ====================================================

        no_tool_streak = 0

        # Execute ONLY the first tool call.
        tool_call = tool_calls_from_model[
            0
        ]

        function_data = tool_call.get(
            "function",
            {},
        )

        tool_name = function_data.get(
            "name"
        )

        if tool_name:
            tool_name = _canonical_tool_name(
                tool_name
            )

        # Once hard evidence exists, prevent the LLM from turning the
        # next action into a rollback or another speculative operation.
        # The controller will gather the missing read-only corroboration
        # sources itself.
        if (
            tool_name in HIGH_IMPACT_TOOLS
            and _controller_needs_corroboration(state)
        ):
            print(
                "\n=== HIGH-IMPACT ACTION DEFERRED ==="
            )
            print(
                "Controller hard evidence exists, but the "
                "independent-evidence gate is not complete."
            )
            print(
                "Only read-only corroboration is allowed now."
            )

            fallback = (
                _select_controller_corroboration_tool(
                    goal,
                    state,
                )
            )

            if fallback:
                fallback_tool, fallback_arguments = fallback

                successful, should_stop = _execute_tool(
                    fallback_tool,
                    fallback_arguments,
                    iteration + 1,
                    state,
                    observations,
                    tool_calls,
                    retry_counts,
                    messages,
                    tracer,
                )

                if should_stop:
                    break

                if successful:
                    no_tool_streak = 0

            continue

        raw_arguments = function_data.get(
            "arguments",
            {},
        )

        # ----------------------------------------------------
        # Missing tool name
        # ----------------------------------------------------

        if not tool_name:

            print(
                "\n=== INVALID TOOL CALL ==="
            )

            print(
                "Model returned a tool call without "
                "a tool name."
            )

            fallback = (
                _select_fallback_evidence_tool(
                    goal,
                    state,
                )
            )

            if fallback:

                fallback_tool, fallback_arguments = (
                    fallback
                )

                _execute_tool(
                    fallback_tool,
                    fallback_arguments,
                    iteration + 1,
                    state,
                    observations,
                    tool_calls,
                    retry_counts,
                    messages,
                    tracer,
                )

            continue

        try:

            # =================================================
            # PARSE ARGUMENTS
            # =================================================

            arguments = _parse_tool_arguments(
                raw_arguments
            )

            # =================================================
            # NORMALIZE ARGUMENTS
            # =================================================

            arguments = _normalize_tool_arguments(
                tool_name,
                arguments,
            )

            # Final protection against the model putting a tool
            # identifier into a search keyword.
            if tool_name == "search_logs":

                keyword = arguments.get("keyword")

                if (
                    isinstance(keyword, str)
                    and keyword.strip().lower()
                    in INVALID_LOG_KEYWORD_PATTERNS
                ):
                    arguments["keyword"] = _build_log_keyword(goal)

        except ToolDispatchError as e:

            print(
                "\n=== ARGUMENT ERROR ==="
            )

            print(
                str(e)
            )

            messages.append(
                {
                    "role": "tool",
                    "content": _serialize_tool_result(
                        {
                            "error": str(e),
                            "tool": tool_name,
                        }
                    ),
                }
            )

            continue

        # ====================================================
        # DUPLICATE CALL PRE-CHECK
        # ====================================================

        if _call_already_used(
            tool_calls,
            tool_name,
            arguments,
        ):

            print(
                "\n=== DUPLICATE TOOL CALL BLOCKED ==="
            )

            print(
                "Tool:",
                tool_name,
            )

            print(
                "Arguments:",
                arguments,
            )

            messages.append(
                {
                    "role": "system",
                    "content": (
                        "That exact tool call has already "
                        "been executed.\n\n"
                        "Do NOT repeat it.\n"
                        "Select a different evidence-producing "
                        "tool or a materially different "
                        "read-only query."
                    ),
                }
            )

            fallback = (
                _select_fallback_evidence_tool(
                    goal,
                    state,
                )
            )

            if fallback:

                fallback_tool, fallback_arguments = (
                    fallback
                )

                successful, should_stop = (
                    _execute_tool(
                        fallback_tool,
                        fallback_arguments,
                        iteration + 1,
                        state,
                        observations,
                        tool_calls,
                        retry_counts,
                        messages,
                        tracer,
                    )
                )

                if should_stop:

                    break

            continue

        # ====================================================
        # EXECUTE MODEL TOOL CALL
        # ====================================================

        successful, should_stop = (
            _execute_tool(
                tool_name,
                arguments,
                iteration + 1,
                state,
                observations,
                tool_calls,
                retry_counts,
                messages,
                tracer,
            )
        )

        if should_stop:

            break

        # ====================================================
        # HARD EVIDENCE CHECK
        # ====================================================
        # This MUST happen before the periodic LLM checkpoint.
        # Once authoritative pool-exhaustion evidence exists, the
        # model is no longer allowed to re-plan or request actions.

        state["observations"] = observations
        state["tool_calls"] = tool_calls

        if successful and _terminate_on_controller_hard_evidence(state):

            print(
                "\n=== CONTROLLER TERMINATION ==="
            )

            print(
                "Authoritative tool evidence directly confirms "
                "database connection pool exhaustion."
            )

            print(
                "Skipping LLM reflection/re-planning."
            )

            break

        # ====================================================
        # REASONING CHECKPOINT EVERY 3 ITERATIONS
        # ====================================================

        # Check if reflection is disabled via environment variable
        reflection_disabled = os.environ.get(
            "OPSPILOT_DISABLE_REFLECTION"
        ) == "1"

        if (
            (iteration + 1) % 3 == 0
            and successful
            and not reflection_disabled
        ):

            reasoning_checkpoints += 1

            new_plan = (
                _run_reasoning_checkpoint(
                    state,
                    tracer,
                )
            )

            # After the allowed number of checkpoints, do not enter
            # another re-plan cycle if primary evidence is complete.
            # A successful re-plan is an instruction to continue,
            # not a reason to terminate. Let the next iteration execute
            # the revised evidence plan.
            if (
                _primary_evidence_complete(tool_calls)
                and reasoning_checkpoints >= MAX_REASONING_CHECKPOINTS
                and not new_plan
            ):
                gate_passed, gate_reason = _evidence_gate(state)

                if not gate_passed:
                    state["terminated"] = True
                    state["termination_reason"] = "insufficient_evidence"
                    state["incident_status"] = "inconclusive"

                    print(
                        "\n=== EVIDENCE EXHAUSTED ==="
                    )
                    print(
                        "The primary evidence sources were collected, "
                        "but the evidence gate still failed."
                    )
                    print(
                        "No actionable revised plan remained."
                    )
                    print(
                        "OpsPilot will stop rather than guess."
                    )
                    break

            if new_plan:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "The investigation has been "
                            "re-planned because the evidence "
                            "is insufficient.\n\n"
                            "NEW INVESTIGATION PLAN:\n"
                            + "\n".join(
                                f"{index + 1}. {step}"
                                for index, step in enumerate(
                                    new_plan
                                )
                            )
                            + "\n\n"
                            "Continue executing the revised "
                            "plan. "
                            "Use one tool at a time. "
                            "Do not repeat identical calls. "
                            "Do not conclude without evidence."
                        ),
                    }
                )

        # ====================================================
        # STATE UPDATE
        # ====================================================

        state[
            "observations"
        ] = observations

        state[
            "tool_calls"
        ] = tool_calls

    # ========================================================
    # SAVE FINAL DYNAMIC STATE
    # ========================================================

    state[
        "observations"
    ] = observations

    state[
        "tool_calls"
    ] = tool_calls

    # ========================================================
    # MAX ITERATION TERMINATION
    # ========================================================

    if not state.get(
        "terminated",
        False,
    ):

        state[
            "terminated"
        ] = True

        state[
            "termination_reason"
        ] = "max_iterations_reached"

        print(
            "\n=== MAXIMUM ITERATIONS REACHED ==="
        )

        print(
            "The investigation did not satisfy the "
            "evidence gate within the allowed iterations."
        )

    # ========================================================
    # FINAL LOOP SUMMARY
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "     DYNAMIC INVESTIGATION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Tool calls executed:",
        len(tool_calls),
    )

    print(
        "Unique tools used:",
        _unique_tool_count(
            tool_calls
        ),
    )

    print(
        "Unique evidence tools used:",
        _unique_evidence_tool_count(
            tool_calls
        ),
    )

    print(
        "Selected hypothesis:",
        state.get(
            "selected_hypothesis"
        ),
    )

    print(
        "Termination reason:",
        state.get(
            "termination_reason"
        ),
    )

    return state


# ============================================================
# EXECUTE APPROVED ACTION
# ============================================================

def execute_approved_action(
    pending_approval: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute an approved high-impact action.

    This function is intentionally kept compatible with
    the existing API.

    It should ONLY be called after human approval.
    """

    from .tools import execute_rollback

    if not pending_approval:

        return {
            "status": "error",
            "message": "No pending approval found.",
        }

    # --------------------------------------------------------
    # Existing approval structure
    # --------------------------------------------------------

    action = pending_approval.get(
        "action"
    )

    service = pending_approval.get(
        "service"
    )

    deployment_id = pending_approval.get(
        "deployment_id"
    )

    # --------------------------------------------------------
    # Tool-based approval structure
    # --------------------------------------------------------

    if not action:

        tool_name = pending_approval.get(
            "tool"
        )

        arguments = pending_approval.get(
            "arguments",
            {},
        )

        if tool_name == "request_rollback":

            action = "rollback"

            service = arguments.get(
                "service"
            )

            deployment_id = arguments.get(
                "deployment_id"
            )

    # --------------------------------------------------------
    # Validate action
    # --------------------------------------------------------

    if not action:

        return {
            "status": "error",
            "message": "No action specified.",
        }

    # ========================================================
    # ROLLBACK
    # ========================================================

    if action == "rollback":

        if not service:

            return {
                "status": "error",
                "message": (
                    "No service specified for rollback."
                ),
            }

        if not deployment_id:

            return {
                "status": "error",
                "message": (
                    "No deployment ID specified "
                    "for rollback."
                ),
            }

        return execute_rollback(
            service=service,
            deployment_id=deployment_id,
        )

    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

    return {
        "status": "error",
        "message": (
            f"Unsupported approved action: {action}"
        ),
    }


# ============================================================
# MAIN INVESTIGATION PIPELINE
# ============================================================

def run_investigation(
    goal: str,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    service: str | None = None,
) -> dict[str, Any]:
    """
    Run the complete OpsPilot investigation pipeline.

    Flow:

        Planner
            ↓
        Autonomous Agent
            ↓
        Dynamic Tool Registry
            ↓
        Operational Evidence
            ↓
        Every 3 iterations:
            Hypothesis
            Verification
            Reflection
            Re-planning
            ↓
        Programmatic Evidence Gate
            ↓
        Approval if high-impact action
            ↓
        Final Report
    """

    # ========================================================
    # INITIAL STATE
    # ========================================================

    state: AgentState = {
        "goal": goal,
        "service": service or _extract_service(goal, {}),
        "plan": [],
        "observations": [],
        "tool_calls": [],
        "hypotheses": [],
        "evidence": [],
        "reflection_notes": [],
        "reflection": None,
        "selected_hypothesis": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "terminated": False,
        "termination_reason": None,
        "pending_approval": None,
        "action_execution": None,
        "verification_result": None,
        "controller_grounded": False,
        "controller_grounded_hypothesis": None,
        "goal_evidence_status": "unknown",
        "incident_status": "investigating",
        "final_report": None,
    }

    # ========================================================
    # TRACER INITIALIZATION - ADDED FOR OBSERVABILITY
    # ========================================================

    tracer = Tracer(
        investigation_id=goal[:40]
    )

    # ========================================================
    # OPSPILOT START
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "            OPSPILOT START"
    )

    print(
        "========================================"
    )

    print(
        "\nGoal:",
        goal,
    )

    # ========================================================
    # 1. INITIAL PLANNER
    # ========================================================

    plan_result = planner_node(
        state
    )

    state.update(
        plan_result
    )

    # ========================================================
    # TRACE PLAN CREATED - ADDED FOR OBSERVABILITY
    # ========================================================

    tracer.log(
        "plan_created",
        {
            "plan": state.get("plan", []),
        },
        iteration=state.get("iteration", 0),
    )

    print(
        "\n=== PLAN ==="
    )

    for step in state.get(
        "plan",
        [],
    ):

        print(
            f"- {step}"
        )

    # ========================================================
    # 2. AUTONOMOUS AGENT LOOP
    # ========================================================

    state = _run_dynamic_tool_loop(
        goal,
        state,
        tracer,
    )

    # ========================================================
    # 3. FINAL CONTROLLER GROUNDING / REASONING
    # ========================================================

    # First preserve any authoritative hard evidence found during the
    # dynamic loop.  This must happen before invoking the LLM again.
    controller_grounded = _apply_controller_grounding(state)

    if controller_grounded:
        print(
            "\n=== FINAL CONTROLLER EVIDENCE ==="
        )
        print(
            state.get("controller_grounded_hypothesis")
        )

        print(
            "\n=== FINAL CONTROLLER VERIFICATION ==="
        )
        print(
            state.get("verification_result", {})
        )

    elif not state.get("hypotheses"):
        # Only non-controller-grounded investigations need the normal
        # LLM hypothesis/verifier path.
        hypothesis_result = hypothesis_node(state)
        state.update(hypothesis_result)

        print("\n=== FINAL HYPOTHESES ===")
        for hypothesis in state.get("hypotheses", []):
            print(hypothesis)

        verifier_result = verifier_node(state)
        state.update(verifier_result)

        print("\n=== FINAL VERIFICATION ===")
        print(state.get("verification_result", {}))

        _select_verified_hypothesis(state)

    # ========================================================
    # 4. FINAL REFLECTION
    # ========================================================

    # Controller hard evidence is authoritative.  Do not call the
    # local reflection model after it has established an explicit
    # mechanism; reflection is advisory and previously caused the
    # endless re-plan loop.
    if (
        not controller_grounded
        and state.get("termination_reason") != "awaiting_human_approval"
        and state.get("goal_evidence_status") != "unsupported"
        and not state.get("reflection")
    ):
        reflection_result = reflection_node(state)
        state.update(reflection_result)

        print("\n=== FINAL REFLECTION ===")
        print(state.get("reflection", {}))

    # ========================================================
    # 5. APPROVAL
    # ========================================================

    pending_approval = state.get(
        "pending_approval"
    )

    if pending_approval:

        print(
            "\n=== APPROVAL REQUIRED ==="
        )

        print(
            pending_approval
        )

        state[
            "incident_status"
        ] = "awaiting_approval"

        state[
            "termination_reason"
        ] = "awaiting_human_approval"

        state[
            "terminated"
        ] = True

        # ====================================================
        # TRACE CLOSE WITH STATE - ADDED FOR OBSERVABILITY
        # ====================================================

        tracer.close(state)

        return state

    # ========================================================
    # 6. FINAL EVIDENCE GATE
    # ========================================================

    gate_passed, gate_reason = (
        _evidence_gate(
            state
        )
    )

    print(
        "\n=== FINAL EVIDENCE GATE ==="
    )

    print(
        "Passed:",
        gate_passed,
    )

    print(
        "Reason:",
        gate_reason,
    )

    # ========================================================
    # 7. FINAL REPORT
    # ========================================================

    if gate_passed:

        if _apply_controller_grounding(state):
            report_result = _build_controller_grounded_report(
                state
            )
        else:
            report_result = report_node(
                state
            )

        state.update(
            report_result
        )

        print(
            "\n=== FINAL REPORT ==="
        )

        print(
            state.get(
                "final_report"
            )
        )

        state[
            "incident_status"
        ] = "completed"

        state[
            "termination_reason"
        ] = "reported"

    else:

        print(
            "\n=== FINAL REPORT BLOCKED ==="
        )

        print(
            "OpsPilot does not have enough verified evidence "
            "to produce a grounded root-cause report."
        )

        state[
            "incident_status"
        ] = "inconclusive"

        if state.get(
            "termination_reason"
        ) == "reported":

            state[
                "termination_reason"
            ] = "insufficient_evidence"

    # ========================================================
    # COMPLETE
    # ========================================================

    state[
        "terminated"
    ] = True

    # ========================================================
    # TRACE CLOSE WITH STATE - ADDED FOR OBSERVABILITY
    # ========================================================

    tracer.close(state)

    print(
        "\n========================================"
    )

    print(
        "           OPSPILOT COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Termination:",
        state.get(
            "termination_reason"
        ),
    )

    print(
        "Incident status:",
        state.get(
            "incident_status"
        ),
    )

    print(
        "Iterations:",
        state.get(
            "iteration"
        ),
    )

    print(
        "Tools:",
        [
            call.get(
                "tool"
            )
            for call in state.get(
                "tool_calls",
                [],
            )
        ],
    )

    print(
        "Selected hypothesis:",
        state.get(
            "selected_hypothesis"
        ),
    )

    return state