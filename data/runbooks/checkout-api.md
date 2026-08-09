# Runbook: checkout-api

## Known failure mode: DB pool exhaustion

Symptoms: p95 latency > 500ms, ERROR logs containing "pool exhausted".

Likely causes: connection pool too small for retry volume, or a recent
deploy that changed retry behavior.

## Immediate actions (read-only, no approval needed)

1. Check `query_metrics` for latency_ms_p95 and error_rate_pct over the incident window.
2. Check `get_deployments` for anything deployed in the last 2 hours.
3. Check `search_incidents` for prior occurrences (e.g. INC-104).

## High-impact action (requires human approval)

- Rolling back a deployment via `request_rollback`.