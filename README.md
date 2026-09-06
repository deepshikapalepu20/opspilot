OpsPilot --- Agentic AI Incident Investigation System

An autonomous, evidence-grounded incident investigation agent for
software operations.

OpsPilot is an agentic AI system designed to investigate
software-service incidents such as latency spikes, error-rate increases,
timeouts, deployment regressions, database connection-pool exhaustion,
missing operational evidence, and historically recurring failures.

Instead of following one fixed diagnostic script, OpsPilot maintains
investigation state, creates an initial plan, selects diagnostic tools,
examines their results, generates root-cause hypotheses, verifies those
hypotheses against collected evidence, reflects on evidence gaps,
re-plans when necessary, and produces a final grounded incident report.

The project was built as an internship/capstone implementation around
the requirements of the OpsPilot Advanced Agentic AI assignment. The
assignment specifically requires a manual agent loop before framework
migration, dynamic tool dispatch, bounded autonomy, RAG, hypothesis
verification, reflection/re-planning, human approval for high-impact
actions, LangGraph migration, trajectory observability, 30+ evaluation
scenarios, failure analysis, UI/API integration, and Docker packaging.

Table of Contents

Project Overview

Problem Being Solved

Why Agentic AI?

Core Investigation Lifecycle

System Architecture

Major Components

Detailed Project Structure

Detailed Explanation of Every Important
File

Tool System

State Management

Planning and Re-Planning

Hypothesis Generation

Evidence Verification

Reflection and Self-Correction

Agentic RAG

Guardrails and Bounded Autonomy

Human-in-the-Loop Approval

LangGraph Migration

LLM Layer

FastAPI Backend

Streamlit UI

Trajectory Logging and
Observability

Evaluation Framework

Evaluation Dataset

Current Evaluation Results

Development Problems and
Solutions

Dockerization

Security and Configuration

Installation

Running the Project

Example Investigation

Known Limitations

Technical Defense Questions

Final Submission Checklist

Project Overview

OpsPilot treats incident investigation as a sequential decision-making
problem.

A user gives the system an investigation goal, for example:

Investigate the checkout-api latency spike after the latest deployment

OpsPilot extracts the affected service, creates an investigation plan,
gathers operational evidence, evaluates hypotheses, checks whether the
evidence is sufficient, and finally returns an incident report.

A simplified execution is:

User Goal
   |
   v
Service / Goal Extraction
   |
   v
Investigation Planner
   |
   v
Agent Loop
   |
   +----> Metrics
   |
   +----> Logs
   |
   +----> Deployments
   |
   +----> Historical Incidents
   |
   +----> Runbook / RAG
   |
   v
Hypothesis Generation
   |
   v
Evidence Verification
   |
   +---- Evidence insufficient ----> Reflection
   |                                      |
   |                                      v
   |                                Re-planning
   |                                      |
   |                                      +----> Agent Loop
   |
   +---- Evidence sufficient
   |
   v
Grounded Incident Report
   |
   +---- High-impact action? ----> Human Approval

The important design principle is that the system does not treat an
LLM-generated explanation as automatically true. A hypothesis must be
checked against operational observations before it can become the
selected root cause.

Problem Being Solved

Traditional incident investigation often requires an engineer to
manually perform a sequence such as:

Check whether the service is currently degraded.

Inspect latency/error metrics.

Search application logs.

Check recent deployments.

Search historical incidents.

Read the service runbook.

Form possible root causes.

Compare each hypothesis with evidence.

Gather additional evidence when the first hypothesis is weak.

Decide whether an operational action should be taken.

This process is time-consuming and can be inconsistent.

OpsPilot automates the investigative reasoning while keeping high-impact
production actions behind a human approval boundary.

The project deliberately separates:

observation,

reasoning,

evidence verification,

reporting,

and production-changing actions.

This separation is important because an agent should not be allowed to
convert an uncertain LLM-generated hypothesis directly into a production
action.

Why Agentic AI?

A deterministic workflow could be written as:

metrics -> logs -> deployments -> incidents -> report

That approach is predictable but inflexible.

Different incidents require different evidence. For example:

A deployment regression needs deployment history and before/after
metrics.

A database pool problem needs logs and database-related metrics.

A historical incident question may need incident search and runbook
retrieval.

A missing-data scenario should result in an inconclusive
investigation rather than an invented root cause.

A red-herring deployment scenario should avoid blaming the latest
deployment simply because it exists.

OpsPilot therefore lets the model select the next diagnostic action
based on the current investigation state.

The agent can:

select different tools,

change the investigation direction,

recognize weak evidence,

generate alternative hypotheses,

request additional evidence,

re-plan,

stop when evidence is sufficient,

or terminate without a grounded report when evidence is
insufficient.

This is the main reason an agentic architecture was selected instead of
one fixed workflow.

Core Investigation Lifecycle

1. Goal interpretation

The system receives an incident goal.

Example:

Investigate checkout-api latency spike after the latest deployment

The service is extracted as:

checkout-api

This service is retained in investigation state so subsequent tool
arguments remain service-specific.

2. Planning

The planner creates an initial investigation plan.

A typical plan can include:

1. Query relevant service metrics.
2. Search service logs for WARN and ERROR messages.
3. Check recent deployments.
4. Search previous incidents.
5. Retrieve the relevant runbook.

The plan is a guide, not a rigid execution sequence.

3. Evidence gathering

The agent selects diagnostic tools and executes them through the dynamic
registry.

4. Hypothesis generation

The hypothesis component proposes one or more candidate causes with
confidence and supporting evidence.

5. Evidence verification

The verifier checks whether the candidate hypotheses are actually
supported by tool-derived or retrieved evidence.

6. Reflection

If evidence is weak, contradictory, or incomplete, reflection identifies
the evidence gap and can trigger re-planning.

7. Re-planning

The planner can generate a revised plan based on what is missing.

8. Finalization

Only after the investigation reaches an acceptable evidence state does
OpsPilot produce the final report.

9. Approval boundary

If the recommended next action has production impact, such as a
rollback, the system stops and waits for explicit human approval.

System Architecture

                         +----------------------+
                         |        User          |
                         |  Incident Goal       |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |     FastAPI / UI     |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |   OpsPilot Agent     |
                         |    Agent Loop        |
                         +----------+-----------+
                                    |
                 +------------------+------------------+
                 |                  |                  |
                 v                  v                  v
          +-------------+    +-------------+    +-------------+
          |   Planner   |    |  Guardrails |    | LLM Layer  |
          +------+------+    +-------------+    +------+------+
                 |                                   |
                 |                                   v
                 |                            +-------------+
                 |                            | Qwen 2.5 3B|
                 |                            |   Ollama   |
                 |                            +-------------+
                 |
                 v
          +-------------+
          | Tool Registry|
          +------+------+
                 |
       +---------+---------+---------+---------+---------+
       |         |         |         |         |         |
       v         v         v         v         v         v
     Logs     Metrics  Deployments Incidents Runbooks  Report/
                                                       Action
       |         |         |         |         |
       +---------+---------+---------+---------+
                           |
                           v
                    +-------------+
                    |  Evidence   |
                    | Verification|
                    +------+------+
                           |
                           v
                    +-------------+
                    | Reflection  |
                    +------+------+
                           |
                 evidence gap?
                    /          \
                  yes           no
                   |             |
                   v             v
              Re-planning     Report
                                  |
                                  v
                         Human Approval Gate
                         for high-impact
                              actions

          RAG subsystem:
          Runbooks + Historical Incidents
                    |
                    v
               ChromaDB
                    ^
                    |
          Sentence Transformer

Major Components

Agent engine

The agent engine is responsible for the iterative investigation cycle.

It coordinates:

state,

planning,

LLM decisions,

tool dispatch,

evidence collection,

hypothesis generation,

verification,

reflection,

approval,

reporting,

termination,

and tracing.

Tools

Tools represent the environment the agent can inspect.

The model does not directly access files or operational data. It
requests a named tool with structured arguments.

Registry

The registry converts a model-selected tool name into a validated Python
function.

This avoids a large hard-coded if/elif dispatcher.

State

State stores everything known about the current investigation.

This includes the goal, service, plan, observations, tool history,
hypotheses, evidence, reflection results, approval state, verification
state, and final report.

Planner

The planner converts the initial incident goal into actionable
investigative steps and can later produce a revised plan.

Hypothesis engine

The hypothesis engine turns collected observations into ranked candidate
root causes.

Verifier

The verifier checks whether hypotheses are actually grounded in
evidence.

Reflection

Reflection acts as a critic. It identifies evidence gaps,
contradictions, skipped investigative checks, and alternative
explanations.

RAG

RAG gives the agent access to operational knowledge such as runbooks and
historical incidents.

Retrieval is agentic: it is invoked when the agent chooses the runbook
retrieval tool instead of running automatically on every request.

Guardrails

Guardrails prevent uncontrolled execution through:

maximum iteration limits,

duplicate-call detection,

retry budgets,

evidence requirements,

controlled tool dispatch,

and approval enforcement.

Approval layer

High-impact actions do not execute automatically.

A rollback request becomes a pending approval instead.

Observability

Every investigation can be written as a JSONL trajectory containing the
sequence of decisions and events.

API

FastAPI exposes the agent to external clients and the Streamlit UI.

UI

Streamlit provides a human-facing interface for entering investigation
goals and viewing results.

Evaluation

The evaluation system runs the agent independently of the UI against a
fixed set of scenarios and calculates investigation metrics.

Detailed Project Structure

opspilot/
│
├── api/
│   └── main.py
│
├── data/
│   ├── incidents.json
│   ├── deployments.json
│   ├── logs/
│   ├── metrics/
│   ├── runbooks/
│   ├── trajectories/
│   ├── reports/
│   ├── vector_store/
│   └── approval_queue.json
│
├── docker/
│   └── docker-compose.yml
│
├── eval/
│   ├── scenarios.json
│   ├── generate_scenarios.py
│   ├── run_eval.py
│   ├── results.json
│   ├── summary.json
│   └── failure_analysis.md
│
├── opspilot/
│   ├── agent_loop.py
│   ├── langgraph_agent.py
│   ├── planner.py
│   ├── hypothesis.py
│   ├── reflection.py
│   ├── verifier.py
│   ├── approval.py
│   ├── guardrails.py
│   ├── registry.py
│   ├── report.py
│   ├── schemas.py
│   ├── state.py
│   ├── tools.py
│   ├── llm.py
│   │
│   ├── observability/
│   │   └── tracer.py
│   │
│   └── rag/
│       ├── ingest.py
│       └── retriever.py
│
├── ui/
│   ├── app.py
│   └── trajectory_viewer.py
│
├── cli.py
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── README.md

venv/, _backup/, and _final_backup/ are development artifacts and
are not part of the runtime architecture.

Detailed Explanation of Every Important File

cli.py

The command-line entry point for running OpsPilot without the web UI.

Why it exists:

The project was initially built as a CLI-oriented agent before the API
and UI layers were added. This makes the core agent independently
executable and easier to debug.

Typical usage:

python .\cli.py

The CLI accepts an investigation goal and displays the investigation
lifecycle, tool calls, evidence, hypotheses, reflection, and final
status.

opspilot/agent_loop.py

This is the central implementation of OpsPilot.

It is responsible for the actual iterative agent behavior.

Major responsibilities include:

initializing investigation state,

extracting/maintaining the affected service,

creating the initial plan,

asking the LLM what to do next,

parsing tool requests,

dispatching tools,

collecting observations,

generating hypotheses,

verifying evidence,

invoking reflection,

triggering re-planning,

enforcing guardrails,

handling fallback actions,

selecting a grounded hypothesis,

generating the final report,

and determining termination.

The manual loop was deliberately implemented first because the
assignment requires understanding the underlying agent loop before
migrating it to LangGraph.

Conceptually:

while not state.terminated:
    increment iteration
    enforce limits
    decide next action

    if action is stop:
        finalize report
        break

    validate tool call
    check duplicates
    check approval
    execute tool
    record observation

    evaluate hypotheses
    verify evidence
    reflect when necessary
    re-plan when necessary

This file became the largest component because the prototype needed
robust handling for small-model behavior, malformed outputs, empty
evidence, duplicate calls, fallback actions, grounding, and termination.

opspilot/langgraph_agent.py

The LangGraph version of the investigation workflow.

The manual loop was built first and then migrated into a graph.

This file demonstrates how the same investigation stages can be
represented as graph nodes and conditional transitions.

Typical conceptual nodes include:

Planner
   |
Tool / Agent Decision
   |
Evidence
   |
Hypothesis
   |
Verification
   |
Reflection
   |
Re-plan or Report
   |
Approval

Why LangGraph is used:

The graph makes state transitions and control flow explicit. It is
easier to reason about a multi-stage agent with branching, looping, and
shared state than an unstructured collection of LLM calls.

The manual implementation remains important because it shows what the
framework abstracts away.

opspilot/planner.py

Responsible for creating investigation plans.

The planner converts a natural-language incident goal into a set of
investigative steps.

It also supports re-planning when reflection identifies an evidence gap.

Why it is separate:

Planning should not be mixed with tool execution. Separating planning
makes the architecture easier to test and allows the agent to
distinguish between the original plan and revised investigative plans.

opspilot/hypothesis.py

Generates candidate root causes from the current investigation context.

A hypothesis contains information such as:

cause
confidence / confidence_pct
supporting_evidence

The model can produce multiple hypotheses instead of immediately
committing to the first explanation.

Why this matters:

Incident investigation is uncertain. Multiple hypotheses reduce the risk
of treating the first plausible explanation as fact.

opspilot/reflection.py

Implements the critic/reflection stage.

Reflection examines:

evidence gaps,

contradictions,

skipped investigative steps,

alternative explanations,

and whether more investigation is required.

Example reflection output:

The leading hypothesis is not sufficiently supported.
Direct evidence of database connection-pool exhaustion is missing.
Additional logs and metrics should be collected.

That reflection can trigger a revised investigation plan.

opspilot/verifier.py

Responsible for evidence-grounded verification.

The verifier receives:

current investigation context,

tool history,

observations,

and hypotheses.

It determines whether each hypothesis is grounded.

A verification result conceptually looks like:

{
  "cause": "Database connection pool exhaustion",
  "grounded": true,
  "gap": ""
}

or:

{
  "cause": "Network failure",
  "grounded": false,
  "gap": "No network evidence was collected"
}

Why it is critical:

Without verification, the LLM could turn a plausible explanation into a
false incident report.

opspilot/approval.py

Implements human-in-the-loop approval.

The project treats high-impact operations differently from read-only
diagnostics.

Read-only operations can execute automatically.

A high-impact action such as rollback is intercepted and recorded as a
pending approval.

The approval record contains information such as:

investigation goal
requested tool
arguments
requested timestamp
approval status

The critical design rule is:

High confidence != automatic permission

The system does not auto-approve a production-changing action merely
because the model has high confidence.

opspilot/guardrails.py

Provides safety and bounded-autonomy controls.

Important mechanisms include:

Maximum iterations

Prevents the investigation from running indefinitely.

Duplicate-call detection

Prevents the agent from repeatedly executing the same diagnostic call
without justification.

Retry budget

Prevents repeated failed tool calls from consuming unlimited iterations.

Empty observation handling

Recognizes results such as empty logs, missing metric points, or empty
retrieval results.

Stop conditions

Allows the system to terminate with an explicit reason such as:

reported
awaiting_human_approval
max_iterations_reached

Why this matters:

An autonomous agent needs a bounded operational envelope.

opspilot/registry.py

The dynamic tool dispatcher.

It maintains a mapping such as:

search_logs      -> tools.search_logs
query_metrics    -> tools.query_metrics
get_deployments  -> tools.get_deployments
search_incidents -> tools.search_incidents
retrieve_runbook -> tools.retrieve_runbook
create_report    -> tools.create_incident_report
request_rollback -> tools.request_rollback

The registry also connects tool names with Pydantic schemas and
identifies high-impact tools.

Why dynamic dispatch is used:

A long if/elif chain would tightly couple the agent to every tool. A
registry allows a new tool to be added through a schema plus registry
entry.

opspilot/report.py

Responsible for constructing the final incident report and
cleaning/normalizing report fields.

A final report can contain:

incident title
likely root cause
confidence
evidence
recommended action
approval requirement
causal boundary

The report layer is also important for preventing accidental
contamination of report fields with raw investigation goals or other
internal text.

One important debugging issue occurred here: a controller-grounded
report path was constructing the root-cause text using the investigation
goal instead of the extracted service name. This produced a report in
which the complete goal appeared inside the root-cause sentence.

The fix was to use the state service:

service_name = str(
    state.get("service")
    or "the affected service"
).strip()

and to ensure service extraction happened during initial state
construction.

opspilot/schemas.py

Contains structured Pydantic schemas for tool arguments and related data
structures.

Why schemas are necessary:

LLMs can produce malformed or ambiguous arguments. A schema provides a
strict interface between the model and the Python tools.

For example, a metrics query needs structured information such as:

service
metric
start
end

The schema layer prevents arbitrary unvalidated model output from being
passed directly into tools.

opspilot/state.py

Defines the investigation state.

The state acts as the shared memory of one investigation.

It can contain:

goal
service
plan
observations
tool_history
hypotheses
evidence
reflection
selected_hypothesis
iteration
max_iterations
termination status
approval state
action execution
verification result
final report
controller grounding information

Why state is essential:

An agent must remember what has already been discovered and what has
already been attempted. Without shared state, each model call would
behave like an isolated request.

opspilot/tools.py

Contains the actual diagnostic tool implementations.

The tools operate over the project's synthetic operational environment.

Important tools include:

search_logs

Searches logs for service-specific messages, levels, keywords, and time
windows.

query_metrics

Queries synthetic metrics such as p95 latency over a specified time
window.

get_deployments

Checks recent deployments affecting a service.

search_incidents

Searches historical incidents for similar symptoms or root causes.

retrieve_runbook

Retrieves operational guidance through the RAG layer.

create_incident_report

Creates/stores structured incident reports.

request_rollback

Represents a production rollback request but does not directly execute
the rollback. The approval layer controls whether the action can
proceed.

Why synthetic tools are used:

The internship project is an agentic prototype, so synthetic operational
data provides a deterministic environment in which tool routing,
reasoning, evidence grounding, and evaluation can be measured
repeatably.

RAG Components

opspilot/rag/ingest.py

Builds the ChromaDB knowledge index.

It processes:

runbooks,

historical incidents.

Runbooks are chunked into smaller sections before embedding.

The embedding model is:

all-MiniLM-L6-v2

The resulting embeddings are stored in a persistent ChromaDB vector
store.

Why chunking is used:

Large documents should not be passed as one huge retrieval unit.
Chunking allows semantically relevant portions to be retrieved.

opspilot/rag/retriever.py

Performs semantic retrieval.

The important design decision is that retrieval is agentic.

The system does not automatically run RAG on every request.

Instead:

Agent decides it needs operational knowledge
        |
        v
retrieve_runbook
        |
        v
semantic search
        |
        v
weak result?
   /          \
 no            yes
 |              |
return       reformulate
result          |
                v
             retry once

The retriever can reformulate a weak query and retry once.

This improves retrieval robustness without creating an unlimited
retrieval loop.

Tool System

OpsPilot separates tool selection from tool execution.

The model is responsible for deciding:

which tool

and:

with which arguments

The registry is responsible for validating and executing that request.

Example:

{
  "tool": "query_metrics",
  "arguments": {
    "metric": "latency_ms_p95",
    "service": "checkout-api",
    "start": "2026-08-03T14:00:00Z",
    "end": "2026-08-03T14:20:00Z"
  }
}

The execution pipeline is:

LLM
 |
 v
Tool name + JSON arguments
 |
 v
Schema validation
 |
 v
Registry lookup
 |
 v
Python function
 |
 v
Observation
 |
 v
State / trajectory

This separation provides a clean boundary between probabilistic model
output and deterministic program execution.

State Management

A typical investigation evolves like this:

Initial State
    |
    +-- goal
    +-- service
    +-- empty observations
    +-- empty hypotheses
    +-- iteration = 0
    |
    v
Plan Added
    |
    v
Tool Result Added
    |
    v
More Tool Results
    |
    v
Hypotheses Added
    |
    v
Verification Added
    |
    v
Reflection Added
    |
    v
Re-plan or Report

The state is also used by the LangGraph implementation as the shared
information passed between graph nodes.

Planning and Re-Planning

The first plan is generated from the user's goal.

However, the agent is not forced to execute every planned step blindly.

Suppose the initial evidence suggests:

Latency increased.

but there is no direct evidence for:

Database connection pool exhaustion.

Reflection can identify this gap.

The planner can then generate:

1. Search for database timeout/pool-related errors.
2. Query additional latency and database-related metrics.
3. Check deployment changes related to database behavior.

This is what makes the workflow adaptive rather than a fixed sequence.

Hypothesis Generation

The model is asked to generate ranked hypotheses rather than a single
answer.

For example:

Hypothesis 1:
Database connection pool exhaustion
Confidence: 90%

Hypothesis 2:
Application concurrency issue
Confidence: 75%

Hypothesis 3:
Network latency
Confidence: 40%

The supporting evidence for each hypothesis is retained.

This allows the verifier to reject hypotheses that are merely plausible
but unsupported.

Evidence Verification

Evidence verification is one of the most important controls in OpsPilot.

The system distinguishes:

Observed fact

from:

Model interpretation

For example:

Observed:
p95 latency increased from approximately 180 ms to 970 ms.

Interpretation:
The database connection pool may have exhausted.

The interpretation cannot automatically be treated as a confirmed root
cause.

The verifier asks:

Is this hypothesis supported by the actual tool observations?

If not, the investigation should continue or remain inconclusive.

Reflection and Self-Correction

Reflection was implemented because an agent can appear confident while
still lacking sufficient evidence.

A representative development trajectory showed:

Metrics showed a latency spike.
Logs returned no matching records.
The model generated a database-related hypothesis.
Verification found that the hypothesis was not grounded.
Reflection identified the missing evidence.
The system triggered re-planning.

This behavior is desirable.

The correct response to missing evidence is:

collect more evidence

not:

invent an explanation

Reflection therefore acts as a control mechanism between reasoning and
reporting.

Guardrails and Bounded Autonomy

An agent can otherwise enter loops such as:

search_logs
search_logs
search_logs
search_logs
...

or:

query_metrics
query_metrics
query_metrics
...

OpsPilot uses guardrails to prevent this.

The system tracks previous calls and can distinguish a justified retry
from an unnecessary duplicate.

It also limits the number of iterations and retries.

Example termination:

termination_reason = max_iterations_reached

This is preferable to allowing an agent to run indefinitely.

Human-in-the-Loop Approval

The system has a strict distinction between:

diagnostic action

and:

production-changing action

Read-only investigation tools can execute automatically.

A rollback is different.

The workflow is:

Agent recommends rollback
          |
          v
Approval check
          |
          v
Pending approval record
          |
          v
Agent stops
          |
     Human decides
       /       \
   Approve     Reject
      |           |
      v           v
 Execute        Stop
      |
      v
 Verify

The system intentionally does not use:

if confidence > 90%:
    auto_approve()

because model confidence is not an authorization mechanism.

LangGraph Migration

The assignment required the manual agent loop to be implemented before
migration.

That requirement was followed.

The development sequence was:

Manual Agent Loop
       |
       v
Validate behavior
       |
       v
Add planning / RAG / verification /
reflection / approval
       |
       v
Migrate the workflow to LangGraph

LangGraph abstracts the mechanics of:

graph state,

node transitions,

conditional routing,

repeated execution,

and termination paths.

The important engineering lesson is that the framework does not replace
the underlying agent logic. The manual implementation made the control
flow explicit first.

LLM Layer

opspilot/llm.py

Provides the interface between OpsPilot and the language model.

The primary local model is:

qwen2.5:3b-instruct

running through Ollama.

The implementation includes:

request handling,

JSON responses,

timeouts,

retry handling,

keep-alive behavior,

and optional Groq fallback.

The local configuration uses:

OLLAMA_URL
MODEL_NAME
OLLAMA_TIMEOUT
OLLAMA_RETRIES
OLLAMA_KEEP_ALIVE

The Dockerized configuration overrides the Ollama URL with:

http://host.docker.internal:11434/api/chat

This allows the container to communicate with Ollama running on the
Windows host.

Why Qwen 2.5 3B?

The project initially used a larger 7B model during development.

The system became too slow/heavy on the available machine, so the
project was moved to:

qwen2.5:3b-instruct

This was an engineering trade-off.

A smaller local model:

reduced local resource usage,

made repeated evaluation more practical,

allowed the project to run on the available hardware,

but it also produced more tool-calling and reasoning inconsistencies
than a larger model.

Instead of hiding this limitation, the project addressed it through:

structured prompts,

schemas,

fallback tool selection,

evidence gates,

reflection,

retry controls,

duplicate-call detection,

controller grounding,

and bounded execution.

FastAPI Backend

api/main.py

Provides the HTTP interface.

The implemented API includes:

GET /

Basic API availability check.

Expected:

{
  "message": "OpsPilot API is running"
}

GET /health

Health check.

Expected:

{
  "status": "healthy"
}

POST /investigate

Starts an investigation.

Example:

{
  "goal": "Investigate the checkout-api latency spike after the latest deployment"
}

The response includes investigation state such as:

goal,

service,

plan,

observations,

tool calls,

hypotheses,

selected hypothesis,

verification,

termination reason,

controller grounding,

and final report.

POST /approve

Handles approval decisions for pending high-impact actions.

The API layer also maintains the latest investigation state for the
prototype.

Streamlit UI

ui/app.py

Provides the user-facing investigation interface.

The UI communicates with the FastAPI backend rather than directly
embedding the agent logic.

This separation is intentional:

Streamlit
   |
   | HTTP
   v
FastAPI
   |
   v
OpsPilot Agent

Benefits:

frontend and backend are separated,

the API can be tested independently,

the same backend can support other clients,

the agent remains independent from UI code.

Trajectory Logging and Observability

opspilot/observability/tracer.py

Records investigation events.

A trajectory is stored as JSONL so each event can be represented
independently.

Typical events include:

plan_created
decision
tool_call
tool_result
hypotheses
verification
reflection
replan
approval
final_state

A final state can contain:

terminated
termination_reason
total_iterations
tool_calls

Why trajectory logging matters:

A final answer alone does not reveal whether the agent behaved
correctly.

Two agents might produce the same root cause while one used:

metrics -> logs -> deployment -> evidence verification

and another used:

random tool calls -> repeated logs -> unsupported guess

Trajectory inspection allows the second behavior to be diagnosed.

Trajectory Viewer

ui/trajectory_viewer.py

Provides a Streamlit inspection interface for saved trajectories.

It allows a reviewer to select an investigation and inspect individual
events.

This is especially useful for:

debugging,

evaluation,

failure analysis,

technical demonstrations,

and explaining the agent's behavior during a defense.

Evaluation Framework

The evaluation pipeline is intentionally independent of the UI.

The assignment requires the evaluation pipeline to measure the quality
of the agent itself rather than relying on manual inspection of the
interface.

The evaluation examines:

Tool selection accuracy

Tool argument accuracy

Investigation success rate

Root-cause accuracy

Average tool calls

Unnecessary tool calls

Loop completion rate

Evidence/controller grounding behavior

The evaluation pipeline executes scenarios, captures the resulting agent
state, scores it against expected outcomes, and writes aggregate
results.

Evaluation Dataset

eval/generate_scenarios.py

Generates the evaluation dataset programmatically.

This was deliberately done instead of manually writing 30 nearly
identical JSON objects.

The scenario generator uses parameterized patterns such as:

bad_deploy
pool_exhaustion
red_herring_no_deploy
missing_data
prior_incident_match

Goals are also varied.

This creates different combinations of:

service,

failure mode,

investigation wording,

expected tools,

expected root-cause indicators,

approval expectations.

eval/scenarios.json

Contains the actual evaluation scenarios.

The project currently contains:

30 scenarios
30 unique scenarios
0 duplicates

The scenarios cover materially different investigation goals rather than
repeating one scenario 30 times.

Examples include:

deployment regression,

database pool exhaustion,

database timeout investigation,

latency/error spikes,

missing evidence,

historical incidents,

runbook grounding,

red-herring deployments,

evidence sufficiency,

rollback recommendations,

complete evidence-grounded investigations.

eval/run_eval.py

Executes the scenarios independently of the UI.

For each scenario it records information such as:

scenario ID
pattern
tools called
tool selection accuracy
tool argument accuracy
unnecessary calls
investigation completion
root-cause correctness
termination reason
approval expectation
approval behavior

It writes:

eval/results.json
eval/summary.json
eval/failure_analysis.md

Current Evaluation Results

The current recorded evaluation summary is:

Metric                             Result

Scenarios                              30
Unique scenarios                       30
Tool selection accuracy             99.2%
Tool argument accuracy              91.4%
Investigation success rate           100%
Root-cause accuracy                  100%
Average tool calls                    4.2
Average unnecessary tool calls        1.0
Loop completion rate                 100%
Approval gating correctness          100%
Controller grounding rate            100%
Average evidence count                1.0

These numbers should be interpreted together with trajectory inspection
and failure analysis. In particular, tool argument accuracy and
unnecessary calls show that the agent still has room for improvement
even though the current scenarios complete successfully.

The current summary should not be described as proof of production
reliability. It is an evaluation of the synthetic scenario environment.

Failure Analysis

eval/failure_analysis.md

Contains representative scenario-level analysis.

The failure-analysis workflow was important during development because
early agent behavior exposed several classes of problems:

incorrect tool selection,

incorrect tool arguments,

unnecessary calls,

repeated calls,

weak evidence,

unsupported hypotheses,

and premature termination.

A representative trajectory showed the model generating a plausible
database hypothesis even though direct log evidence was missing.

The verifier correctly marked the hypothesis as insufficiently grounded,
and reflection identified the evidence gap.

This type of trajectory is valuable because it demonstrates why the
verifier and reflection components exist.

Development Problems and Solutions

This project required substantial debugging because the local 3B model
was less reliable than a larger hosted model for structured tool use.

Problem 1 --- 7B model made the system too slow

Symptom

The initial local model was a 7B variant. Running the agent repeatedly
consumed significant system resources and made development/evaluation
slow.

Solution

The project was moved to:

qwen2.5:3b-instruct

The smaller model made local iteration more practical.

Engineering trade-off

The smaller model was less reliable at:

tool selection,

structured arguments,

and long investigative reasoning.

The project therefore needed additional deterministic controls.

Problem 2 --- The small model sometimes returned no tool call

Symptom

The agent would reach an evidence-gathering stage but the model would
respond without requesting a tool.

Why it mattered

If the investigation simply accepted that response, the workflow could
stop without enough evidence.

Solution

The agent loop includes fallback evidence actions when the model fails
to provide a usable tool request.

The fallback is constrained by the investigation state rather than being
an unrestricted arbitrary action.

Problem 3 --- Empty logs caused weak hypotheses

Symptom

A tool could legitimately return:

count: 0
logs: []

The model could still generate a plausible root cause.

Solution

Empty observations are explicitly recognized by the guardrail/evidence
logic.

The verifier checks whether the hypothesis is actually supported.

If evidence is insufficient, reflection can trigger re-planning instead
of allowing the system to report an unsupported cause.

Problem 4 --- The agent could repeat the same tool

Symptom

The model sometimes selected the same diagnostic operation repeatedly.

Example:

search_logs
search_logs
search_logs
...

Solution

The guardrail layer tracks previous calls and blocks unnecessary
duplicate calls unless the retry is justified.

A retry budget also prevents infinite retry behavior.

Problem 5 --- Investigations reached the maximum iteration limit

Symptom

Some early trajectories ended with:

max_iterations_reached

without a grounded root cause.

This happened when the model repeatedly failed to gather the evidence
required by the evidence gate.

Solution

The system was strengthened with:

better fallback evidence actions,

service-aware tool arguments,

evidence-gathering priorities,

duplicate prevention,

reflection,

re-planning,

and controller-level grounding.

The maximum-iteration limit remains as a safety boundary rather than
being removed.

Problem 6 --- The model produced unsupported root causes

Symptom

The model could infer a reasonable cause from a metric spike even when
no direct evidence supported that cause.

For example:

Latency increased
        ↓
Model guesses database timeout

without an actual database timeout observation.

Solution

The verifier was introduced as an explicit grounding stage.

The final report is allowed to proceed only when the selected hypothesis
meets the project's grounding requirements.

This prevents:

plausible != proven

from becoming a report-generation rule.

Problem 7 --- Reflection itself could generate weak search terms

Symptom

A reflected evidence gap could be translated into a poor search keyword.

A trajectory showed a fallback log query containing a phrase derived
from the re-planning text rather than a clean operational keyword.

Solution

The agent loop was strengthened with controller/fallback logic that
chooses more controlled evidence actions when the model output is
unusable.

This is a practical example of why a small model should not be given
unrestricted control over every part of the system.

Problem 8 --- Service was missing from the API investigation state

Symptom

The API investigation initially returned an empty service field even
though the goal clearly contained:

checkout-api

The report therefore did not have a clean service identifier available.

Root cause

The FastAPI call invoked:

run_investigation(normalized_goal)

without explicitly passing a service.

The initial state was therefore created with an empty service value.

Solution

The initial state construction was changed so that the service is
extracted from the goal when one is not explicitly supplied:

"service": service or _extract_service(goal, {}),

This made the resulting state correctly contain:

service: checkout-api

Problem 9 --- Root-cause report contained the entire investigation goal

Symptom

The final report initially produced text resembling:

Database connection pool exhaustion ... contributed to
Investigate the checkout-api latency spike after the latest deployment
latency.

The full investigation goal had accidentally entered the root-cause
sentence.

Root cause

The controller-grounded report builder used the goal as the service
name.

Solution

The report construction was changed to use:

state["service"]

with a safe fallback:

the affected service

The corrected output became:

Database connection pool exhaustion caused DB write timeouts
and likely contributed to the observed checkout-api latency.

This was also re-tested through the FastAPI endpoint.

Problem 10 --- Uvicorn appeared not to reflect a code change immediately

Symptom

A code change was made, but the running API still appeared to use old
behavior.

Cause

The Uvicorn development process had stale runtime state.

Solution

The server was cleanly restarted:

Ctrl+C

then:

uvicorn api.main:app --reload

The API was tested again after the restart.

Problem 11 --- Docker daemon was initially unavailable

Symptom

The first Docker build returned:

failed to connect to the docker API
dockerDesktopLinuxEngine
The system cannot find the file specified

Cause

Docker Desktop's Linux engine was not running.

Solution

Docker Desktop was started and the Docker daemon was verified before
rebuilding.

The second build proceeded normally.

Problem 12 --- Docker build took a very long time

Symptom

The Docker build spent a long time downloading large ML dependencies.

The build included large packages such as:

torch
nvidia-cudnn
nvidia-cublas
nvidia-nccl
CUDA-related packages

Cause

sentence-transformers depends on PyTorch, and the Linux environment
resolved a large PyTorch dependency stack.

Important observation

The Docker container does not need to run the Qwen model itself.

Qwen remains on the host through Ollama.

The architecture is:

Docker
  |
  | HTTP
  v
host.docker.internal:11434
  |
  v
Ollama
  |
  v
qwen2.5:3b-instruct

The first successful image build was allowed to complete so the Docker
cache could be reused.

Problem 13 --- Container could not use localhost to reach host Ollama

Symptom

Inside a container,:

localhost

refers to the container itself, not the Windows host.

Solution

The Ollama URL was made configurable.

Instead of only using a hard-coded URL, the LLM layer now supports:

OLLAMA_URL = os.environ.get(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)

Local execution continues to use localhost.

Docker Compose overrides it with:

http://host.docker.internal:11434/api/chat

This allows the same application code to run both locally and inside
Docker.

Problem 14 --- .env should not be copied into the Docker image

Symptom/risk

The Dockerfile uses:

COPY . .

Without an ignore file, this could copy .env into the image.

Solution

A .dockerignore file was created containing entries such as:

.env
venv
.venv
__pycache__
.git
_backup
_final_backup

This keeps secrets and development artifacts out of the image build
context.

Dockerization

Dockerfile

The Dockerfile uses:

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

Each instruction has a purpose.

FROM python:3.11-slim

Provides a lightweight Python 3.11 runtime.

WORKDIR /app

Makes /app the working directory.

COPY requirements.txt .

Copies dependency definitions separately so Docker can cache the
dependency installation layer.

RUN pip install ...

Installs the Python dependencies inside the image.

COPY . .

Copies the application source into the image.

The .dockerignore prevents secrets and unnecessary development files
from being copied.

EXPOSE 8000

Documents the FastAPI port.

CMD

Starts Uvicorn when the container starts.

docker/docker-compose.yml

Compose defines the API service and its runtime configuration.

The current configuration maps:

host port 8000
        |
        v
container port 8000

It also passes:

OLLAMA_URL
GROQ_API_KEY
GROQ_MODEL

and configures host access using:

host.docker.internal

Docker Verification

The Docker deployment was tested end-to-end.

The image successfully built.

The container successfully started.

The following API checks passed:

GET /health

returned:

{
  "status": "healthy"
}

The root endpoint returned:

{
  "message": "OpsPilot API is running"
}

The actual investigation endpoint also completed successfully from the
container.

A tested investigation produced:

service:
checkout-api

incident_status:
completed

termination_reason:
reported

controller_grounded:
true

confidence:
90%

The container logs showed:

Application startup complete.
Uvicorn running on http://0.0.0.0:8000

No startup errors were present.

Security and Configuration

The project separates secrets from source code.

The Groq API key is supplied through an environment variable:

GROQ_API_KEY

It should never be hard-coded into Python files or committed to Git.

.env is excluded from the Docker build context.

The agent also separates read-only diagnostics from high-impact
operations.

The most important security boundaries are:

LLM output
   |
   v
Schema validation
   |
   v
Tool registry
   |
   v
Guardrails
   |
   v
Approval boundary for high-impact actions

This prevents the LLM from directly executing arbitrary Python
functions.

Installation

1. Clone/open the project

Open the project directory:

cd C:\Users\deeps\opspilot

2. Create the virtual environment

python -m venv venv

3. Activate it

.\venv\Scripts\Activate.ps1

4. Install dependencies

pip install -r requirements.txt

The project pins the main dependencies, including:

openai
fastapi
uvicorn
pydantic
sqlmodel
chromadb
sentence-transformers
streamlit
python-dotenv
rich
pytest
langgraph

Ollama Setup

Install and start Ollama.

Verify the model:

ollama list

The required model is:

qwen2.5:3b-instruct

If it is missing:

ollama pull qwen2.5:3b-instruct

The local API is:

http://localhost:11434/api/chat

Environment Variables

Create .env when using Groq:

GROQ_API_KEY=your_key
GROQ_MODEL=openai/gpt-oss-20b

Groq is optional.

The local Qwen/Ollama configuration remains available.

Building the RAG Index

Run:

python -m opspilot.rag.ingest

This creates/updates the ChromaDB vector store.

Re-run ingestion after changing the runbooks or historical incident
knowledge.

Running the CLI

Run:

python .\cli.py

Enter an investigation goal.

Example:

Investigate checkout-api latency spike

Running FastAPI

Run:

uvicorn api.main:app --reload

API:

http://127.0.0.1:8000

Swagger documentation:

http://127.0.0.1:8000/docs

Health check:

Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method GET

Running an Investigation through FastAPI

Example:

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/investigate" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"goal":"Investigate the checkout-api latency spike after the latest deployment"}'

Running Streamlit

Start the main UI:

streamlit run .\ui\app.py

The Streamlit application normally opens at:

http://localhost:8501

Running the Trajectory Viewer

Run:

streamlit run .\ui\trajectory_viewer.py

Select an investigation trajectory and inspect its events.

Running the Evaluation

Run:

python -m eval.run_eval

Results are written to:

eval/results.json
eval/summary.json
eval/failure_analysis.md

Running Docker

Make sure Docker Desktop is running.

Build:

docker compose -f .\docker\docker-compose.yml build

Start:

docker compose -f .\docker\docker-compose.yml up -d

Check:

docker compose -f .\docker\docker-compose.yml ps

Health:

Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method GET

Logs:

docker compose -f .\docker\docker-compose.yml logs --tail=100

Stop:

docker compose -f .\docker\docker-compose.yml down

Example Investigation

Input:

Investigate the checkout-api latency spike after the latest deployment

The system identifies:

Service:
checkout-api

An example investigation plan is:

1. Query relevant service metrics.
2. Search service logs.
3. Check recent deployments.
4. Search previous incidents.
5. Retrieve relevant operational knowledge.

The system may gather:

Logs
Metrics
Deployment history
Historical incident information
Runbook evidence

The hypothesis engine can identify:

Database connection pool exhaustion caused DB write timeouts
and contributed to the observed service latency.

The verifier checks the hypothesis against the collected evidence.

The final report includes:

Root cause
Confidence
Evidence
Recommended action
Causal boundary
Approval requirement

The causal boundary is important because the system should distinguish:

What is supported

from:

What is merely inferred

For example, evidence may support database pool exhaustion contributing
to latency without proving that a specific deployment change caused the
exhaustion.

Known Limitations

OpsPilot is a prototype and has several limitations.

Synthetic environment

The operational tools use project data rather than live production
systems such as Kubernetes, Prometheus, cloud APIs, or production log
infrastructure.

Small local model

Qwen 2.5 3B was selected for local hardware constraints. Larger models
may provide stronger tool-calling and reasoning behavior.

Tool argument accuracy

The current evaluation shows strong but imperfect tool argument
accuracy.

The agent can still produce arguments that are semantically reasonable
but do not exactly match the expected benchmark arguments.

Unnecessary tool calls

The agent can occasionally investigate more broadly than required.

This is measurable through the unnecessary-call metric.

RAG dependency

Retrieval quality depends on the quality of runbooks and historical
incidents in the knowledge base.

No live production execution

The rollback action is represented through an approval-controlled
prototype flow. The project is not a live production deployment system.

Prototype approval storage

Approval state is represented using a local JSON queue rather than a
production database.

Evaluation limitations

The evaluation contains 30 synthetic scenarios. High scores demonstrate
performance on this benchmark, not guaranteed production reliability.

Technical Defense Questions

Why was an agent selected instead of a deterministic workflow?

Because incident investigation is not always a fixed sequence. The
required evidence changes depending on the incident, and an agent can
select the next action based on observations.

Where can the agent enter a wasteful loop?

Potentially during repeated tool selection, failed retrieval, or
repeated attempts to resolve an evidence gap.

The project controls this with:

duplicate-call detection,

retry budgets,

maximum iterations,

evidence gates,

and explicit termination.

How is tool-routing accuracy evaluated?

The evaluation compares the tools actually called with the expected
tools defined for each scenario.

How are malformed tool arguments handled?

Tool arguments are validated against structured Pydantic schemas before
dispatch.

What happens when evidence is missing?

The verifier can mark a hypothesis as ungrounded. Reflection identifies
the gap and can trigger re-planning. If sufficient evidence cannot be
obtained within the bounded investigation, the system terminates without
pretending certainty.

Why is reflection included?

Because an LLM can produce a plausible answer before the investigation
has gathered sufficient evidence. Reflection provides an explicit
critique stage that can identify missing evidence and trigger additional
investigation.

How are duplicate calls prevented?

The agent maintains tool-call history and the guardrail layer checks
whether a proposed call has already been made, allowing only justified
retries.

Why was LangGraph added after the manual loop?

The assignment required the manual loop first. Building it manually made
the underlying control flow explicit. LangGraph was then used to
represent the same stateful workflow as a graph with nodes and
conditional transitions.

Why does Docker not contain the Qwen model?

The project uses Ollama as an external host service. Docker packages the
OpsPilot application while communicating with Ollama through
host.docker.internal.

Why is human approval required?

A language model's confidence is not an authorization mechanism.
Production-changing actions require explicit human consent.

Final Submission Checklist

The project now contains the major assignment deliverables:

Agentic incident investigation system

Manual agent loop

Dynamic tool registry

Structured tool schemas

Investigation state

Planning

Bounded autonomy

Duplicate-call prevention

Retry controls

RAG knowledge layer

Agentic retrieval

Query reformulation

Hypothesis generation

Evidence verification

Reflection

Re-planning

Human approval

LangGraph migration

Trajectory logging

Trajectory viewer

30 unique evaluation scenarios

Automated evaluation

Failure analysis

FastAPI API

Streamlit UI

Docker packaging

Docker end-to-end verification

Health endpoint verification

Investigation endpoint verification

Before final submission, the remaining documentation/demo items should
be checked against the assignment rubric, especially the
reflection-on/off comparison if it is required by the final technical
review, the final architecture diagram, the final demo video, and the
cleanliness of the GitHub repository.

Project Outcome

OpsPilot demonstrates a complete agentic incident-investigation pipeline
rather than only an LLM chatbot.

The system combines:

LLM reasoning
+
tool use
+
structured schemas
+
persistent investigation state
+
planning
+
RAG
+
hypothesis generation
+
evidence verification
+
reflection
+
re-planning
+
guardrails
+
human approval
+
observability
+
evaluation
+
API/UI integration
+
Docker deployment

The most important engineering principle implemented throughout the
project is:

The agent may reason autonomously,
but it must operate inside deterministic boundaries.

The LLM provides flexible reasoning and tool-selection behavior.

The surrounding software provides:

validation,

state,

evidence controls,

safety boundaries,

termination,

observability,

and evaluation.

That combination is what makes OpsPilot an agentic AI engineering
project rather than a simple LLM application.