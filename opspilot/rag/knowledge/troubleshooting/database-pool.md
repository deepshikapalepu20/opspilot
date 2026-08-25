# Database Connection Pool Troubleshooting

## Symptoms

Connection pool problems may appear as:

- Pool exhaustion
- Connection acquisition delays
- Database write timeouts
- Increased API latency
- Retry amplification

## Investigation

Check the following:

1. Connection pool utilization
2. Connection acquisition wait time
3. Active connections
4. Database write timeout frequency
5. Retry count
6. Retry backoff
7. Recent application deployments

## Evidence Interpretation

An explicit log such as:

"DB write timeout after retries (pool exhausted)"

is direct operational evidence that connection pool exhaustion occurred.

Latency measurements should be used to determine whether the condition coincided with service degradation.

Deployment information should be used to establish temporal correlation with configuration or code changes.

Deployment correlation alone does not prove causation.

## Remediation

Do not make production-changing configuration changes solely from historical documentation.

Collect current operational evidence first.