# Deployment and Database Retry Behavior

## Retry Wrappers

A retry wrapper around database writes can cause additional database activity when an initial database operation fails or times out.

## Connection Pools

Connection-pool configuration affects the number of database connections available to application instances.

## Investigation Principle

When latency increases after a deployment:

- Establish the deployment timestamp.
- Compare it with the beginning of degradation.
- Identify changes introduced by the deployment.
- Verify the suspected mechanism using live operational evidence.

A deployment occurring before an incident establishes temporal correlation but does not independently prove causation.