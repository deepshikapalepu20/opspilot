# Checkout API Runbook

## Service

Service name: checkout-api

## Purpose

checkout-api handles checkout requests and performs database writes as part of the checkout workflow.

## Common Symptoms

Typical symptoms include:

- Increased p95 latency
- Database write timeouts
- Connection pool exhaustion
- Increased retry activity
- Checkout request failures

## Database Connection Pool Investigation

When checkout-api experiences increased latency:

1. Check database connection pool utilization.
2. Check connection wait time.
3. Check database write timeout errors.
4. Check retry activity.
5. Compare latency before and after recent deployments.
6. Check whether deployment changes modified retry behavior or connection-pool configuration.

## Retry Wrapper Investigation

Retry wrappers around database writes can increase database pressure when requests are already experiencing connection contention.

Check:

- Number of retries
- Retry frequency
- Retry backoff behavior
- Connection pool utilization
- Connection acquisition wait time
- Database write timeout frequency

## Recommended Investigation

Do not immediately change production configuration.

First collect:

- Connection pool utilization
- Connection wait time
- DB write timeout count
- Retry count
- p95 latency
- Recent deployment information

Use the collected operational evidence to establish the root cause before performing remediation.