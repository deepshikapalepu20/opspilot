import json
from pathlib import Path


OUTPUT = Path("eval/scenarios.json")


# ============================================================
# FIXTURE-BACKED EVALUATION SCENARIOS
# ============================================================
#
# The fixture dataset is centered around checkout-api and
# contains evidence for:
#
#   - latency increase
#   - error-rate increase
#   - DB write timeouts
#   - connection-pool exhaustion
#   - retry-wrapper deployment
#   - Redis connection failure
#   - historical incident INC-104
#
# The evaluation suite therefore varies the INVESTIGATION
# CONDITION and EXPECTED BEHAVIOR rather than inventing
# unsupported production incidents.
#
# Each scenario contains:
#
#   scenario_id
#   goal
#   service
#   pattern
#   expected_root_cause_keywords
#   expected_tools
#   expected_arguments
#   requires_approval_expected
#   expected_termination
#
# ============================================================


# ============================================================
# COMMON FIXTURE VALUES
# ============================================================

SERVICE = "checkout-api"

INCIDENT_START = "2026-08-03T14:00:00Z"
INCIDENT_END = "2026-08-03T14:20:00Z"

DEPLOYMENT_SINCE = "2026-08-01T00:00:00Z"

DEPLOYMENT_ID = "checkout-v2.4"


# ============================================================
# SCENARIO DEFINITIONS
# ============================================================

SCENARIOS = [

    # ========================================================
    # 1-4: DEPLOYMENT CORRELATION
    # ========================================================

    {
        "scenario_id": "SCN-001",
        "goal": (
            "Investigate the checkout-api latency spike "
            "after the latest deployment"
        ),
        "pattern": "deployment_correlation",
        "expected_root_cause_keywords": [
            "retry",
            "pool",
            "connection",
        ],
        "expected_tools": [
            "get_deployments",
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "get_deployments": {
                "service": SERVICE,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-002",
        "goal": (
            "Determine whether checkout-v2.4 caused the "
            "checkout-api degradation"
        ),
        "pattern": "deployment_correlation",
        "expected_root_cause_keywords": [
            "retry",
            "connection pool",
            "pool exhausted",
        ],
        "expected_tools": [
            "get_deployments",
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "get_deployments": {
                "service": SERVICE,
                "since": DEPLOYMENT_SINCE,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-003",
        "goal": (
            "Correlate the checkout-api performance regression "
            "with recent deployment activity"
        ),
        "pattern": "deployment_correlation",
        "expected_root_cause_keywords": [
            "retry wrapper",
            "retry",
            "pool",
        ],
        "expected_tools": [
            "get_deployments",
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "get_deployments": {
                "service": SERVICE,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-004",
        "goal": (
            "Investigate whether a deployment introduced the "
            "database retry-related checkout-api failure"
        ),
        "pattern": "deployment_correlation",
        "expected_root_cause_keywords": [
            "retry",
            "connection pool",
            "pool exhausted",
        ],
        "expected_tools": [
            "get_deployments",
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "get_deployments": {
                "service": SERVICE,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 5-8: CONNECTION POOL / DATABASE TIMEOUTS
    # ========================================================

    {
        "scenario_id": "SCN-005",
        "goal": (
            "Investigate checkout-api database connection "
            "pool exhaustion"
        ),
        "pattern": "pool_exhaustion",
        "expected_root_cause_keywords": [
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "pool",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-006",
        "goal": (
            "Determine why checkout-api database writes are "
            "timing out"
        ),
        "pattern": "db_timeout",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-007",
        "goal": (
            "Investigate repeated checkout-api database "
            "timeouts and determine the underlying resource issue"
        ),
        "pattern": "db_timeout",
        "expected_root_cause_keywords": [
            "pool exhausted",
            "connection pool",
            "retry",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-008",
        "goal": (
            "Check whether database connection contention "
            "explains the checkout-api incident"
        ),
        "pattern": "pool_exhaustion",
        "expected_root_cause_keywords": [
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "pool",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 9-12: LATENCY INVESTIGATION
    # ========================================================

    {
        "scenario_id": "SCN-009",
        "goal": (
            "Investigate why checkout-api p95 latency "
            "increased during the incident window"
        ),
        "pattern": "latency_investigation",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "connection pool",
            "DB write timeout",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
            "get_deployments",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "get_deployments": {
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-010",
        "goal": (
            "Determine the cause of the checkout-api p95 "
            "latency spike"
        ),
        "pattern": "latency_investigation",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "DB write timeout",
            "retry",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-011",
        "goal": (
            "Investigate the relationship between elevated "
            "checkout-api latency and database failures"
        ),
        "pattern": "latency_investigation",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-012",
        "goal": (
            "Assess whether the observed checkout-api "
            "latency increase is explained by DB timeouts"
        ),
        "pattern": "latency_investigation",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhaustion",
            "connection pool",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 13-16: ERROR RATE
    # ========================================================

    {
        "scenario_id": "SCN-013",
        "goal": (
            "Investigate the checkout-api error-rate spike"
        ),
        "pattern": "error_rate_investigation",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhaustion",
            "retry",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-014",
        "goal": (
            "Determine why checkout-api errors increased "
            "during the incident"
        ),
        "pattern": "error_rate_investigation",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhausted",
            "retry",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
            "get_deployments",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "get_deployments": {
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-015",
        "goal": (
            "Correlate the checkout-api error-rate increase "
            "with database timeout failures"
        ),
        "pattern": "error_rate_investigation",
        "expected_root_cause_keywords": [
            "timeout",
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-016",
        "goal": (
            "Diagnose the checkout-api error degradation "
            "using metrics and logs"
        ),
        "pattern": "error_rate_investigation",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "DB write timeout",
            "retry",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 17-20: QUERY REFORMULATION / RED-HERRING EVIDENCE
    # ========================================================

    {
        "scenario_id": "SCN-017",
        "goal": (
            "Investigate checkout-api latency and recover "
            "if the initial log search returns no useful evidence"
        ),
        "pattern": "query_reformulation",
        "expected_root_cause_keywords": [
            "pool exhausted",
            "DB write timeout",
            "retry",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-018",
        "goal": (
            "Investigate checkout-api latency while accounting "
            "for the absence of logs containing the word latency"
        ),
        "pattern": "empty_observation_recovery",
        "expected_root_cause_keywords": [
            "pool exhausted",
            "timeout",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "latency",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-019",
        "goal": (
            "Investigate checkout-api degradation and distinguish "
            "the Redis connection failure from the primary DB issue"
        ),
        "pattern": "red_herring",
        "expected_root_cause_keywords": [
            "DB write timeout",
            "pool exhausted",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-020",
        "goal": (
            "Determine whether the checkout-api cache failure "
            "or database pool exhaustion better explains the incident"
        ),
        "pattern": "contradictory_evidence",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "DB write timeout",
            "connection pool",
        ],
        "expected_tools": [
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "error_rate_pct",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 21-23: HISTORICAL INCIDENT RETRIEVAL
    # ========================================================

    {
        "scenario_id": "SCN-021",
        "goal": (
            "Find a historical incident matching checkout-api "
            "database retries and connection-pool exhaustion"
        ),
        "pattern": "historical_incident",
        "expected_root_cause_keywords": [
            "INC-104",
            "retry-wrapper",
            "connection pool",
        ],
        "expected_tools": [
            "search_incidents",
        ],
        "expected_arguments": {
            "search_incidents": {
                "keyword": "retry",
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-022",
        "goal": (
            "Determine whether a previous checkout-api incident "
            "had the same retry-wrapper failure mode"
        ),
        "pattern": "historical_incident",
        "expected_root_cause_keywords": [
            "INC-104",
            "retry-wrapper",
            "connection pool",
        ],
        "expected_tools": [
            "search_incidents",
        ],
        "expected_arguments": {
            "search_incidents": {
                "keyword": "retry-wrapper",
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-023",
        "goal": (
            "Compare the current checkout-api database retry "
            "symptoms with known historical incidents"
        ),
        "pattern": "historical_incident",
        "expected_root_cause_keywords": [
            "INC-104",
            "retry",
            "connection pool",
        ],
        "expected_tools": [
            "search_incidents",
        ],
        "expected_arguments": {
            "search_incidents": {
                "keyword": "connection pool",
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 24-26: RUNBOOK / RAG GROUNDING
    # ========================================================

    {
        "scenario_id": "SCN-024",
        "goal": (
            "Use the checkout-api runbook to investigate "
            "database pool exhaustion"
        ),
        "pattern": "runbook_grounding",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "connection pool",
            "retry",
        ],
        "expected_tools": [
            "retrieve_runbook",
            "search_logs",
            "query_metrics",
        ],
        "expected_arguments": {
            "retrieve_runbook": {
                "query": "database connection pool exhaustion",
                "service": SERVICE,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-025",
        "goal": (
            "Retrieve operational guidance relevant to the "
            "checkout-api retry and timeout failure"
        ),
        "pattern": "runbook_grounding",
        "expected_root_cause_keywords": [
            "retry",
            "pool exhaustion",
            "connection pool",
        ],
        "expected_tools": [
            "retrieve_runbook",
        ],
        "expected_arguments": {
            "retrieve_runbook": {
                "query": "retry wrapper database timeout",
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-026",
        "goal": (
            "Ground the checkout-api investigation in relevant "
            "operational runbook knowledge before recommending action"
        ),
        "pattern": "runbook_grounding",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "retry",
            "connection pool",
        ],
        "expected_tools": [
            "retrieve_runbook",
            "search_logs",
        ],
        "expected_arguments": {
            "retrieve_runbook": {
                "query": "checkout-api latency database retries",
                "service": SERVICE,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 27-28: EVIDENCE SUFFICIENCY
    # ========================================================

    {
        "scenario_id": "SCN-027",
        "goal": (
            "Determine whether the available checkout-api "
            "metrics and logs provide enough evidence for diagnosis"
        ),
        "pattern": "evidence_sufficiency",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "DB write timeout",
            "connection pool",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },

    {
        "scenario_id": "SCN-028",
        "goal": (
            "Assess whether the evidence supports a confident "
            "root-cause conclusion rather than an unsupported guess"
        ),
        "pattern": "evidence_validation",
        "expected_root_cause_keywords": [
            "pool exhaustion",
            "DB write timeout",
            "evidence",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
            "get_deployments",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "get_deployments": {
                "service": SERVICE,
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },


    # ========================================================
    # 29: APPROVAL REQUIRED
    # ========================================================

    {
        "scenario_id": "SCN-029",
        "goal": (
            "Investigate the checkout-api incident and determine "
            "whether rollback of checkout-v2.4 should be recommended"
        ),
        "pattern": "approval_required",
        "expected_root_cause_keywords": [
            "retry",
            "pool exhaustion",
            "connection pool",
            "checkout-v2.4",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
            "get_deployments",
            "request_rollback",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "get_deployments": {
                "service": SERVICE,
            },
            "request_rollback": {
                "service": SERVICE,
                "deployment_id": DEPLOYMENT_ID,
            },
        },
        "requires_approval_expected": True,
        "expected_termination": "awaiting_human_approval",
    },


    # ========================================================
    # 30: HISTORICAL + RUNBOOK + EVIDENCE
    # ========================================================

    {
        "scenario_id": "SCN-030",
        "goal": (
            "Perform a complete evidence-grounded investigation "
            "of checkout-api using metrics, logs, deployment history, "
            "historical incidents, and operational guidance"
        ),
        "pattern": "full_investigation",
        "expected_root_cause_keywords": [
            "retry",
            "pool exhaustion",
            "connection pool",
            "INC-104",
        ],
        "expected_tools": [
            "query_metrics",
            "search_logs",
            "get_deployments",
            "search_incidents",
            "retrieve_runbook",
        ],
        "expected_arguments": {
            "query_metrics": {
                "service": SERVICE,
                "metric": "latency_ms_p95",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "search_logs": {
                "service": SERVICE,
                "level": "ERROR",
                "keyword": "timeout",
                "start": INCIDENT_START,
                "end": INCIDENT_END,
            },
            "get_deployments": {
                "service": SERVICE,
            },
            "search_incidents": {
                "service": SERVICE,
                "keyword": "retry",
            },
            "retrieve_runbook": {
                "service": SERVICE,
                "query": "database retry connection pool",
            },
        },
        "requires_approval_expected": False,
        "expected_termination": "reported",
    },
]


# ============================================================
# VALIDATION
# ============================================================

def validate_scenarios(scenarios: list[dict]):

    if len(scenarios) < 30:
        raise ValueError(
            f"Expected at least 30 scenarios, got {len(scenarios)}"
        )

    scenario_ids = [
        scenario["scenario_id"]
        for scenario in scenarios
    ]

    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError(
            "Duplicate scenario IDs detected."
        )

    required_fields = {
        "scenario_id",
        "goal",
        "service",
        "pattern",
        "expected_root_cause_keywords",
        "expected_tools",
        "expected_arguments",
        "requires_approval_expected",
        "expected_termination",
    }

    for scenario in scenarios:

        missing = required_fields - set(
            scenario.keys()
        )

        if missing:
            raise ValueError(
                f"{scenario['scenario_id']} missing fields: "
                f"{sorted(missing)}"
            )

        if not scenario["expected_tools"]:
            raise ValueError(
                f"{scenario['scenario_id']} has no expected tools."
            )

        for tool_name in scenario["expected_arguments"]:

            if tool_name not in scenario["expected_tools"]:
                raise ValueError(
                    f"{scenario['scenario_id']}: "
                    f"expected_arguments contains "
                    f"'{tool_name}' which is not in "
                    f"expected_tools."
                )


# ============================================================
# DISTRIBUTION
# ============================================================

def print_distribution(scenarios: list[dict]):

    distribution = {}

    for scenario in scenarios:

        pattern = scenario["pattern"]

        distribution[pattern] = (
            distribution.get(pattern, 0) + 1
        )

    print()
    print("Scenario distribution:")

    for pattern, count in distribution.items():

        print(
            f"  {pattern}: {count}"
        )


# ============================================================
# GENERATE
# ============================================================

def generate():

    scenarios = []

    for scenario in SCENARIOS:

        scenario = scenario.copy()

        scenario["service"] = SERVICE

        scenarios.append(
            scenario
        )

    validate_scenarios(
        scenarios
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            scenarios,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Wrote {len(scenarios)} scenarios "
        f"to {OUTPUT}"
    )

    print_distribution(
        scenarios
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    generate()