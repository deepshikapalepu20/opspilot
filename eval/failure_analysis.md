# OpsPilot — Failure Analysis

This report contains representative failures identified during the automated evaluation.

Total scenarios: 30
Failures detected: 12

## SCN-004 — deployment_correlation

**Goal:** Investigate whether a deployment introduced the database retry-related checkout-api failure

**Expected root-cause keywords:** ['retry', 'connection pool', 'pool exhausted']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.9

**Expected arguments:** {'get_deployments': {'service': 'checkout-api'}, 'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'error_rate_pct', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 0

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-005 — pool_exhaustion

**Goal:** Investigate checkout-api database connection pool exhaustion

**Expected root-cause keywords:** ['pool exhausted', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.89

**Expected arguments:** {'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'pool', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'latency_ms_p95', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 1

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-006 — db_timeout

**Goal:** Determine why checkout-api database writes are timing out

**Expected root-cause keywords:** ['DB write timeout', 'pool exhausted', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.89

**Expected arguments:** {'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'error_rate_pct', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 1

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-008 — pool_exhaustion

**Goal:** Check whether database connection contention explains the checkout-api incident

**Expected root-cause keywords:** ['pool exhausted', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.89

**Expected arguments:** {'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'pool', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'latency_ms_p95', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 1

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-020 — contradictory_evidence

**Goal:** Determine whether the checkout-api cache failure or database pool exhaustion better explains the incident

**Expected root-cause keywords:** ['pool exhaustion', 'DB write timeout', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.88

**Expected arguments:** {'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'error_rate_pct', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 1

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-021 — historical_incident

**Goal:** Find a historical incident matching checkout-api database retries and connection-pool exhaustion

**Expected root-cause keywords:** ['INC-104', 'retry-wrapper', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.5

**Expected arguments:** {'search_incidents': {'keyword': 'retry', 'service': 'checkout-api'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_incidents', 'search_logs', 'query_metrics', 'get_deployments']

**Tool calls:** 4

**Unnecessary calls:** 3

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-023 — historical_incident

**Goal:** Compare the current checkout-api database retry symptoms with known historical incidents

**Expected root-cause keywords:** ['INC-104', 'retry', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.5

**Expected arguments:** {'search_incidents': {'keyword': 'connection pool', 'service': 'checkout-api'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['search_incidents', 'search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 5

**Unnecessary calls:** 3

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-024 — runbook_grounding

**Goal:** Use the checkout-api runbook to investigate database pool exhaustion

**Expected root-cause keywords:** ['pool exhaustion', 'connection pool', 'retry']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.91

**Expected arguments:** {'retrieve_runbook': {'query': 'database connection pool exhaustion', 'service': 'checkout-api'}, 'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'query_metrics': {'service': 'checkout-api', 'metric': 'latency_ms_p95', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['retrieve_runbook', 'search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 5

**Unnecessary calls:** 1

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-025 — runbook_grounding

**Goal:** Retrieve operational guidance relevant to the checkout-api retry and timeout failure

**Expected root-cause keywords:** ['retry', 'pool exhaustion', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.5

**Expected arguments:** {'retrieve_runbook': {'query': 'retry wrapper database timeout', 'service': 'checkout-api'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['retrieve_runbook', 'search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 5

**Unnecessary calls:** 3

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-026 — runbook_grounding

**Goal:** Ground the checkout-api investigation in relevant operational runbook knowledge before recommending action

**Expected root-cause keywords:** ['pool exhaustion', 'retry', 'connection pool']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.86

**Expected arguments:** {'retrieve_runbook': {'query': 'checkout-api latency database retries', 'service': 'checkout-api'}, 'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['retrieve_runbook', 'search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 5

**Unnecessary calls:** 2

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-029 — approval_required

**Goal:** Investigate the checkout-api incident and determine whether rollback of checkout-v2.4 should be recommended

**Expected root-cause keywords:** ['retry', 'pool exhaustion', 'connection pool', 'checkout-v2.4']

**Root cause correct:** True

**Tool selection accuracy:** 0.75

**Tool argument accuracy:** 0.83

**Expected arguments:** {'query_metrics': {'service': 'checkout-api', 'metric': 'latency_ms_p95', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'get_deployments': {'service': 'checkout-api'}, 'request_rollback': {'service': 'checkout-api', 'deployment_id': 'checkout-v2.4'}}

**Investigation completed:** True

**Termination:** awaiting_human_approval

**Tools used:** ['search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 4

**Unnecessary calls:** 0

**Controller grounded:** True

**Approval expected:** True

**Approval actual:** True

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.

## SCN-030 — full_investigation

**Goal:** Perform a complete evidence-grounded investigation of checkout-api using metrics, logs, deployment history, historical incidents, and operational guidance

**Expected root-cause keywords:** ['retry', 'pool exhaustion', 'connection pool', 'INC-104']

**Root cause correct:** True

**Tool selection accuracy:** 1.0

**Tool argument accuracy:** 0.86

**Expected arguments:** {'query_metrics': {'service': 'checkout-api', 'metric': 'latency_ms_p95', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'search_logs': {'service': 'checkout-api', 'level': 'ERROR', 'keyword': 'timeout', 'start': '2026-08-03T14:00:00Z', 'end': '2026-08-03T14:20:00Z'}, 'get_deployments': {'service': 'checkout-api'}, 'search_incidents': {'service': 'checkout-api', 'keyword': 'retry'}, 'retrieve_runbook': {'service': 'checkout-api', 'query': 'database retry connection pool'}}

**Investigation completed:** True

**Termination:** reported

**Tools used:** ['retrieve_runbook', 'search_incidents', 'search_logs', 'query_metrics', 'get_deployments', 'search_logs']

**Tool calls:** 6

**Unnecessary calls:** 0

**Controller grounded:** True

**Approval expected:** False

**Approval actual:** False

**Approval gating correct:** True

### Proposed improvement

Inspect the corresponding trajectory under `data/trajectories/` using the trajectory viewer. Determine whether the failure originated from tool selection, tool argument extraction, evidence retrieval, hypothesis generation, verification, reflection, approval gating, or termination.
