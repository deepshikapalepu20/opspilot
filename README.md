🛰️ OpsPilot

Autonomous Incident Investigation Agent for Evidence-Grounded SRE Workflows

OpsPilot is an agentic AI system that investigates service
incidents, gathers operational evidence, tests competing hypotheses,
verifies conclusions, reflects on incomplete investigations, and stops
at a human-approval boundary before high-impact actions.

<p align="center">

Observe → Investigate → Verify → Reflect → Re-plan → Report →
Approve

</p>










⚡ The 30-Second Version

Traditional incident automation often follows a fixed sequence:

Check metrics → check logs → check deployment → write report

OpsPilot is designed around a different question:

"What evidence do I need next to confidently explain this
incident?"

The agent starts with an investigation goal, chooses operational tools,
observes their results, maintains hypotheses and state, checks whether
the evidence actually supports a conclusion, and can change its
investigation path when evidence is insufficient.

For a representative checkout-api latency incident, OpsPilot can
connect:

Recent deployment
      ↓
Retry wrapper around DB writes
      ↓
Database connection pressure
      ↓
DB write timeouts / pool exhaustion
      ↓
Increasing p95 latency
      ↓
Evidence-grounded incident report

The important part is not merely generating the final sentence. The
system records and evaluates how it arrived there.

🎯 What Problem Does OpsPilot Solve?

When a production service becomes slow or starts returning errors, an
engineer may need to inspect several sources:

deployment history

service metrics

application logs

historical incidents

operational runbooks

troubleshooting documentation

The investigation is therefore not just a question-answering task.

It is a sequential decision problem:

What should I inspect?
        ↓
What did I learn?
        ↓
Which hypothesis is now more plausible?
        ↓
What evidence is still missing?
        ↓
Which tool should I call next?
        ↓
Is the evidence strong enough to report?
        ↓
If not → reflect and investigate again

OpsPilot packages that reasoning loop into a reproducible agentic
system.

🧠 Why This Is Agentic AI

OpsPilot is not simply an LLM placed in front of a collection of tools.

The system has:

Agent capability                    OpsPilot implementation

Goal interpretation                 Investigation goal + service
extraction

Planning                            Planner / controller

Tool selection                      Metrics, logs, deployments and
retrieval tools

State                               Structured investigation state

Hypothesis generation               Candidate root-cause hypotheses

Evidence gathering                  Tool execution + retrieved
operational knowledge

Verification                        Evidence gate / verifier

Reflection                          Critique of incomplete or weak
investigations

Re-planning                         New evidence requests when needed

Safety                              Guardrails + approval boundary

Observability                       Trajectory tracing

Evaluation                          Automated 30-scenario benchmark

The central design principle is:

Autonomy is useful only when the system can justify its next action
and ground its final conclusion in evidence.

🏗️ Architecture

High-Level System

                         ┌──────────────────────┐
                         │       USER           │
                         │ Investigation Goal   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   OpsPilot Agent     │
                         │ Controller / Loop    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      PLANNER         │
                         │ What should we do?   │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
              ┌──────────┐   ┌──────────┐     ┌──────────────┐
              │ Metrics  │   │  Logs    │     │ Deployments  │
              └────┬─────┘   └────┬─────┘     └──────┬───────┘
                   │              │                   │
                   └──────────────┼───────────────────┘
                                  │
                                  ▼
                         ┌──────────────────────┐
                         │   RAG / Knowledge    │
                         │ Runbooks / Incidents │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    HYPOTHESIS        │
                         │ Candidate root causes│
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      VERIFIER        │
                         │ Is evidence enough?  │
                         └──────────┬───────────┘
                                    │
                       ┌────────────┴────────────┐
                       │                         │
                 Evidence weak              Evidence strong
                       │                         │
                       ▼                         ▼
                ┌──────────────┐         ┌──────────────┐
                │  REFLECTION  │         │    REPORT    │
                │ Critique gap │         │ Root cause   │
                └──────┬───────┘         │ Evidence     │
                       │                 │ Recommendation│
                       ▼                 └──────┬───────┘
                ┌──────────────┐                │
                │   RE-PLAN    │                ▼
                │ Gather more  │       ┌──────────────────┐
                │ evidence     │       │ HUMAN APPROVAL   │
                └──────┬───────┘       │ High-impact     │
                       │                │ actions         │
                       └───────►        └──────────────────┘

LangGraph-Oriented Flow

flowchart TD
    A[Investigation Goal] --> B[Controller]
    B --> C[Planner]
    C --> D{Choose Tool}
    D --> E[query_metrics]
    D --> F[search_logs]
    D --> G[get_deployments]
    D --> H[retrieve_runbook]
    D --> I[retrieve_incident]

    E --> J[Update State]
    F --> J
    G --> J
    H --> J
    I --> J

    J --> K[Hypothesis]
    K --> L[Verifier]
    L --> M{Evidence Sufficient?}

    M -- No --> N[Reflection / Critic]
    N --> O[Re-plan]
    O --> D

    M -- Yes --> P[Controller-Grounded Report]
    P --> Q{High-Impact Action?}
    Q -- Yes --> R[Human Approval]
    Q -- No --> S[Complete]
    R --> S

🔍 The Investigation Loop

OpsPilot behaves like an investigation state machine rather than a
single prompt.

┌───────────────┐
│  GOAL         │
└───────┬───────┘
        ▼
┌───────────────┐
│ PLAN          │
└───────┬───────┘
        ▼
┌───────────────┐
│ CALL TOOL     │◄──────────────────────────┐
└───────┬───────┘                           │
        ▼                                   │
┌───────────────┐                           │
│ OBSERVE       │                           │
└───────┬───────┘                           │
        ▼                                   │
┌───────────────┐                           │
│ UPDATE STATE  │                           │
└───────┬───────┘                           │
        ▼                                   │
┌───────────────┐                           │
│ HYPOTHESIZE   │                           │
└───────┬───────┘                           │
        ▼                                   │
┌───────────────┐                           │
│ VERIFY        │                           │
└───────┬───────┘                           │
        │                                   │
    ┌───┴─────────────┐                     │
    │                 │                     │
  Weak              Strong                  │
    │                 │                     │
    ▼                 ▼                     │
REFLECT            REPORT                   │
    │                 │                     │
    ▼                 ▼                     │
RE-PLAN          APPROVAL                   │
    │                                       │
    └───────────────────────────────────────┘

This loop is where the project earns its "agentic" characterization.

🧩 Core Components

1. Controller / Agent Loop

opspilot/agent_loop.py

The controller coordinates the investigation.

It is responsible for:

reading the current state

selecting or enforcing investigation actions

executing tools

updating evidence

checking termination conditions

preventing wasteful loops

grounding the final report in the controller-selected hypothesis

A key implementation lesson was that the final report must preserve
the controller's investigation boundary. Otherwise an LLM-generated
phrase can accidentally replace the actual service/incident context.

2. Planner

opspilot/planner.py

The planner translates the investigation goal into operational actions.

Example:

Goal:
Investigate checkout-api latency after the latest deployment

Possible plan:
1. Inspect deployments
2. Query latency metrics
3. Search relevant error logs
4. Retrieve troubleshooting knowledge
5. Compare evidence
6. Verify root cause
7. Report

The planner is not treated as a one-shot script. It can participate in a
re-planning cycle when evidence is incomplete.

3. Hypothesis Engine

opspilot/hypothesis.py

The system maintains candidate explanations instead of immediately
committing to the first plausible answer.

For example:

H1: Database connection pool exhaustion
H2: Redis contention
H3: Deployment regression
H4: Network latency

Evidence can increase or decrease the credibility of these explanations.

The objective is not to generate the most convincing sentence.

The objective is to select the explanation best supported by the
available evidence.

4. Evidence Verifier

opspilot/verifier.py

The verifier acts as a gate between:

“I saw some interesting observations”

and:

“I have enough evidence to make a conclusion.”

This distinction is critical.

A model may produce a plausible root cause even when:

a tool returned no data

evidence is contradictory

a deployment is unrelated

the time window is wrong

the retrieved document does not support the claim

OpsPilot therefore treats evidence sufficiency as a separate concern.

5. Reflection / Critic

opspilot/reflection.py

Reflection asks:

"What is missing from the current investigation?"

Examples of reflection outcomes:

Evidence is too weak.
→ Query another source.

Deployment evidence exists but causal link is unclear.
→ Inspect metrics around deployment time.

Logs are sparse.
→ Retrieve a runbook or historical incident.

Current hypothesis is plausible but not sufficiently supported.
→ Continue investigation.

Reflection is therefore used as a control mechanism, not merely as
decorative chain-of-thought.

📚 RAG: Operational Knowledge

OpsPilot includes a local retrieval layer for operational knowledge.

Relevant knowledge categories include:

opspilot/rag/knowledge/
│
├── architecture/
│   └── deployment-and-retries.md
│
├── incidents/
│   └── INC-104.md
│
├── runbooks/
│   └── checkout-api.md
│
└── troubleshooting/
    └── database-pool.md

The retrieval layer is implemented through:

opspilot/rag/loader.py
opspilot/rag/ingest.py
opspilot/rag/retriever.py

This gives the agent access to operational context without hard-coding
every troubleshooting rule into the controller.

Why RAG matters

A metric may show:

Latency increased.

A log may show:

DB write timeout.

A runbook can provide the operational interpretation:

Connection pool exhaustion can cause DB write contention
and propagate into request latency.

RAG therefore helps bridge the gap between raw observations and
operational knowledge.

🛠️ Tooling Layer

OpsPilot's tools provide the agent with controlled access to the
incident environment.

Tool                                Purpose

query_metrics                     Inspect service metrics over a time
window

search_logs                       Search service logs for relevant
events

get_deployments                   Inspect recent deployments

retrieve_runbook                  Retrieve operational guidance

retrieve_incident                 Retrieve historical incident
context

Tool arguments are validated rather than blindly trusted.

The tool layer is implemented primarily in:

opspilot/tools.py
opspilot/schemas.py
opspilot/guardrails.py

🛡️ Safety and Human Approval

OpsPilot separates:

Investigation

from:

Operational action

An agent can investigate autonomously, but an impactful action should
not automatically execute just because an LLM recommended it.

The approval boundary is implemented through:

opspilot/approval.py

Conceptually:

AI investigates
      ↓
AI recommends
      ↓
Is action high-impact?
      │
   ┌──┴──┐
   │     │
  No    Yes
   │     │
   ▼     ▼
Execute  HUMAN APPROVAL
         │
     ┌───┴────┐
     │        │
  Approve   Reject
     │        │
     └───┬────┘
         ▼
      Continue

This gives the system a clear autonomy boundary.

🤖 LLM Strategy

OpsPilot supports a local-first LLM path with an optional Groq path.

The implementation is in:

opspilot/llm.py

Current design:

                 ┌───────────────┐
                 │ LLM Request   │
                 └───────┬───────┘
                         │
                 ┌───────▼────────┐
                 │ Groq available?│
                 └───────┬────────┘
                    Yes  │  No
                         │
              ┌──────────▼───┐
              │ Groq / hosted│
              └──────────────┘
                         │
                         ▼
                  Ollama fallback
                         │
                         ▼
              qwen2.5:3b-instruct

The local fallback uses:

qwen2.5:3b-instruct

This was deliberately kept lightweight enough for local development.

The Ollama endpoint is configurable through:

OLLAMA_URL

so Docker can communicate with a host-side Ollama service using:

host.docker.internal

without breaking normal local Windows execution.

📊 Evaluation

OpsPilot is evaluated against 30 unique scenarios.

The dataset was designed to vary the investigation objective rather than
repeating one incident pattern.

Examples of scenario families include:

deployment regressions

database pool exhaustion

database timeout investigations

latency spikes

error-rate spikes

missing or insufficient logs

Redis vs database hypotheses

historical incident retrieval

runbook/RAG investigations

evidence sufficiency checks

rollback recommendations

complete evidence-grounded investigations

Current evaluation snapshot

Metric                                  Result

Scenarios                               30
Unique scenarios                   30 / 30
Duplicate scenarios                      0
Tool selection accuracy              99.2%
Tool argument accuracy               91.4%
Investigation success rate            100%
Root-cause accuracy                   100%
Loop completion rate                  100%
Approval gating correctness           100%
Controller grounding rate             100%
Average tool calls                     4.2
Average unnecessary tool calls         1.0
Average evidence count                 1.0

These are benchmark results on the project's controlled scenario set,
not a claim of production reliability.

The raw artifacts are stored in:

eval/scenarios.json
eval/results.json
eval/summary.json
eval/failure_analysis.md

🧪 Evaluation Pipeline

Run the evaluation with:

python -m eval.run_eval

The pipeline produces:

eval/
├── results.json
├── summary.json
└── failure_analysis.md

The scenario generator is:

eval/generate_scenarios.py

The evaluator measures more than "did the model say the right answer?"

It also examines:

Tool selection
Tool arguments
Investigation completion
Root-cause correctness
Tool-call efficiency
Loop completion
Approval gating
Controller grounding
Evidence

This makes the evaluation closer to an agent evaluation problem than
a simple text-generation benchmark.

🔭 Observability: The Agent's Flight Recorder

Agentic systems can be difficult to debug because the final answer hides
the path taken to reach it.

OpsPilot therefore records investigation trajectories.

The tracing implementation lives in:

opspilot/observability/tracer.py

And the inspection interface lives in:

ui/trajectory_viewer.py

A trajectory can expose information such as:

Iteration 1
    ↓
Tool selected
    ↓
Arguments
    ↓
Tool result
    ↓
State update
    ↓
Hypothesis
    ↓
Verifier decision
    ↓
Next action

This makes failures inspectable.

Instead of asking:

"Why did the agent get this answer?"

we can ask:

"At which iteration did the investigation diverge?"

That is a much more useful debugging question.

🖥️ User Interfaces

OpsPilot provides a Streamlit interface:

ui/app.py

and a separate trajectory viewer:

ui/trajectory_viewer.py

The Streamlit application provides an interactive way to submit
investigation goals and inspect returned findings.

The trajectory viewer is focused on agent behavior and investigation
traces.

🌐 FastAPI

The backend API is implemented in:

api/main.py

Available endpoints include:

GET  /
GET  /health
POST /investigate
POST /approve

Health check

GET /health

Response:

{
  "status": "healthy"
}

Investigation

POST /investigate
Content-Type: application/json

{
  "goal": "Investigate the checkout-api latency spike after the latest deployment"
}

The response contains investigation information such as:

service
incident_status
termination_reason
controller_grounded
hypothesis
root_cause
confidence
evidence

Interactive API documentation is available through FastAPI's generated
Swagger interface at:

http://127.0.0.1:8000/docs

🐳 Docker

OpsPilot is packaged for reproducible backend execution.

Files:

Dockerfile
docker/docker-compose.yml
.dockerignore

The container:

Python 3.11
    ↓
Dependencies
    ↓
OpsPilot source
    ↓
Uvicorn
    ↓
FastAPI

The container exposes:

8000

The Docker setup also supports communication with a host-side Ollama
service through:

host.docker.internal:11434

Build and start

From the project root:

docker compose -f docker/docker-compose.yml up --build

Verify

Invoke-RestMethod http://127.0.0.1:8000/health

Expected:

{
  "status": "healthy"
}

Then open:

http://127.0.0.1:8000/docs

Stop

docker compose -f docker/docker-compose.yml down

🚀 Local Setup

1. Clone the repository

git clone https://github.com/deepshikapalepu20/opspilot.git
cd opspilot

2. Create a virtual environment

python -m venv venv

Activate it on PowerShell:

.\venv\Scripts\Activate.ps1

3. Install dependencies

pip install -r requirements.txt

4. Configure environment variables

Copy:

.env.example

to:

.env

Never commit .env.

The repository's .gitignore intentionally excludes local secrets and
development artifacts.

5. Start Ollama

Make sure the required local model is available:

ollama run qwen2.5:3b-instruct

6. Start the API

uvicorn api.main:app --reload

Then visit:

http://127.0.0.1:8000/docs

🧪 Example Investigation

Input:

Investigate the checkout-api latency spike after the latest deployment

OpsPilot can investigate the incident through evidence such as:

Deployment
──────────
checkout-v2.4
Added retry wrapper around DB writes
Bumped connection pool size


Metrics
───────
p95 latency:
180 ms → 185 ms → 640 ms → 910 ms → 970 ms


Logs
────
DB write timeout after 3 retries
(pool exhausted)


Hypothesis
──────────
Database connection pool exhaustion
caused DB write timeouts and contributed
to the observed service latency.

The final report should preserve the causal scope of the investigation:

checkout-api latency
        ↑
database connection pressure
        ↑
DB write retries / pool exhaustion

rather than accidentally turning an entire user prompt into the
root-cause label.

🧯 Engineering Problems We Encountered

This project was not built as a single successful run. Several
implementation issues had to be identified and corrected.

Problem 1 --- Controller report used the entire goal as the service

An early implementation effectively did:

service_name = goal

This caused a report to potentially produce a root cause containing the
entire investigation goal.

Fix

The report now derives the service from structured state:

state["service"]

with service extraction performed during investigation initialization.

This keeps the final report scoped to the actual affected service.

Problem 2 --- Service existed in the goal but not in initialized state

The service extractor could correctly identify:

checkout-api

but the initial investigation state could still contain an empty service
value.

Fix

The initial state now uses the extracted service when an explicit
service value is unavailable.

This allows downstream controller-grounded reporting to use the correct
causal boundary.

Problem 3 --- Docker could not reach local Ollama

Inside a container:

localhost

refers to the container itself, not the Windows host running Ollama.

Fix

The Ollama endpoint became environment-configurable.

Docker uses:

http://host.docker.internal:11434/api/chat

while local development retains:

http://localhost:11434/api/chat

Problem 4 --- Backup files were mixed with repository artifacts

During development, multiple backup and generated files accumulated.

Examples:

*.backup
*_backup.*
data/trajectories/
eval/latest_results.json

Fix

Repository hygiene was enforced through .gitignore.

The final repository intentionally excludes:

.env
venv/
__pycache__/
backup files
generated trajectories
temporary test scripts

while retaining reproducible evaluation artifacts.

Problem 5 --- Trajectory viewer filename typo

An earlier file was named:

tarjectory_viewer.py

The final version is:

trajectory_viewer.py

The typo was removed during repository cleanup.

🧱 Project Structure

opspilot/
│
├── api/
│   └── main.py
│
├── data/
│   ├── logs.json
│   └── ...
│
├── docker/
│   └── docker-compose.yml
│
├── eval/
│   ├── failure_analysis.md
│   ├── generate_scenarios.py
│   ├── results.json
│   ├── run_eval.py
│   ├── scenarios.json
│   └── summary.json
│
├── opspilot/
│   ├── agent_loop.py
│   ├── approval.py
│   ├── guardrails.py
│   ├── hypothesis.py
│   ├── langgraph_agent.py
│   ├── llm.py
│   ├── planner.py
│   ├── reflection.py
│   ├── registry.py
│   ├── report.py
│   ├── schemas.py
│   ├── state.py
│   ├── tools.py
│   ├── verifier.py
│   │
│   ├── observability/
│   │   └── tracer.py
│   │
│   └── rag/
│       ├── ingest.py
│       ├── loader.py
│       ├── retriever.py
│       └── knowledge/
│
├── ui/
│   ├── app.py
│   └── trajectory_viewer.py
│
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── cli.py
└── requirements.txt

🗺️ File Responsibility Map

File                           Responsibility

agent_loop.py                Core investigation controller
langgraph_agent.py           LangGraph-oriented agent flow
planner.py                   Investigation planning
hypothesis.py                Candidate root-cause reasoning
verifier.py                  Evidence sufficiency
reflection.py                Critique and missing-evidence reasoning
state.py                     Structured investigation state
tools.py                     Operational tool implementations
schemas.py                   Structured data / validation models
guardrails.py                Safety and tool-use constraints
approval.py                  Human approval boundary
report.py                    Investigation report generation
llm.py                       LLM provider integration
registry.py                  Tool/component registration
observability/tracer.py      Trajectory and execution tracing
rag/loader.py                Knowledge loading
rag/ingest.py                Retrieval index ingestion
rag/retriever.py             Knowledge retrieval
api/main.py                  FastAPI service
ui/app.py                    Streamlit UI
ui/trajectory_viewer.py      Trajectory inspection UI
eval/run_eval.py             Automated evaluation
eval/scenarios.json          30 evaluation scenarios
eval/generate_scenarios.py   Scenario generation
eval/failure_analysis.md     Failure-analysis documentation
cli.py                       Command-line entry point
Dockerfile                   Container image definition
docker/docker-compose.yml    Docker runtime configuration

🧭 Design Principles

1. Evidence before confidence

A plausible answer is not enough.

Observation ≠ Evidence
Evidence ≠ Causality
Causality → Verified conclusion

The verifier exists to enforce this distinction.

2. Investigation before intervention

OpsPilot can investigate autonomously.

High-impact operational actions remain behind an approval boundary.

3. State over hidden context

Important investigation information should live in structured state
rather than relying on the model to remember everything from a long
conversation.

4. Trajectories are first-class artifacts

The final answer is only one output.

The investigation path is another.

5. Evaluate the agent, not just the answer

A good agent should:

choose useful tools
+ provide valid arguments
+ gather evidence
+ terminate cleanly
+ avoid waste
+ respect approval boundaries
+ produce a correct conclusion

📈 What the Evaluation Actually Tells Us

The current benchmark is strong on the controlled scenario set:

30 / 30 scenarios completed
30 / 30 scenarios unique
100% root-cause accuracy
100% loop completion
100% approval-gating correctness
100% controller grounding
99.2% tool selection accuracy
91.4% tool argument accuracy

But there are still meaningful areas for improvement.

Evidence density

The current benchmark reports:

Average evidence count: 1.0

That suggests a useful next step is to evaluate whether investigations
should gather multiple independent evidence sources before terminating.

Tool efficiency

The benchmark reports:

Average unnecessary tool calls: 1.0

This means future optimization should focus on reducing redundant
investigation steps without sacrificing evidence quality.

Reflection measurement

The assignment specifically calls for measuring whether reflection
improves performance.

A proper next experiment is:

30 scenarios
      │
      ├── Reflection ON
      │
      └── Reflection OFF
              ↓
Compare:
root-cause accuracy
loop completion
tool calls
failure modes

That comparison should be treated as an experimental result rather than
assuming reflection is beneficial simply because it exists.

🔬 Failure Analysis

The project includes:

eval/failure_analysis.md

The purpose is to inspect representative trajectories rather than only
looking at aggregate scores.

A useful failure-analysis workflow is:

Scenario failure
      ↓
Open trajectory
      ↓
Find first incorrect decision
      ↓
Classify failure
      ↓
Identify missing guardrail / state / evidence
      ↓
Implement improvement
      ↓
Re-run benchmark

Typical agent failure categories include:

Wrong tool
Wrong arguments
Premature termination
Insufficient evidence
Redundant tool call
Incorrect hypothesis
Poor causal grounding
Approval boundary error

🔐 Security and Repository Hygiene

The repository intentionally does not contain:

.env
venv/
__pycache__/
local databases
vector-store runtime artifacts
generated trajectory logs
temporary test scripts
backup copies

Use:

.env.example

as the configuration template.

Never put API keys directly into Python source code or commit them to
Git.

🧰 Technology Stack

Layer                 Technology

Language              Python 3.11
Agent orchestration   LangGraph
LLM                   Qwen 2.5 3B via Ollama
Hosted LLM path       Groq-compatible API path
API                   FastAPI
UI                    Streamlit
Retrieval             ChromaDB / sentence-transformers
Validation            Pydantic
Data models           SQLModel
Containerization      Docker
Testing               Pytest
Evaluation            Custom scenario/evaluation pipeline
Observability         Custom trajectory tracer

🧪 Useful Commands

Run the API

uvicorn api.main:app --reload

Run Streamlit

streamlit run ui/app.py

Run trajectory viewer

streamlit run ui/trajectory_viewer.py

Run evaluation

python -m eval.run_eval

Docker build and run

docker compose -f docker/docker-compose.yml up --build

Docker shutdown

docker compose -f docker/docker-compose.yml down

Git status

git status

🧪 Example API Test

PowerShell:

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/investigate" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"goal":"Investigate the checkout-api latency spike after the latest deployment"}'

A successful investigation should return a completed incident with a
controller-grounded finding.

🧠 Technical Defense Cheat Sheet

Why use an agent instead of a deterministic workflow?

Because the next useful investigation action depends on evidence
discovered during previous actions.

A fixed workflow assumes:

A → B → C → D

An agent can reason:

A → evidence
      ↓
      B or C?
      ↓
      evidence insufficient
      ↓
      D
      ↓
      re-plan

The investigation path therefore adapts to observations.

Where can the agent loop wastefully?

Potentially when:

it repeatedly requests similar tools

it cannot establish evidence sufficiency

it keeps generating unsupported hypotheses

it fails to recognize that no additional evidence is useful

OpsPilot mitigates this through state, iteration limits, tool-call
tracking, verification, reflection and termination logic.

How are malformed tool arguments handled?

Tool schemas and guardrails constrain the structure of tool requests
before execution.

What if retrieved documentation contains prompt injection?

Retrieved content should be treated as evidence/data, not as trusted
instructions. Retrieval results must not override system-level tool or
safety rules.

Why is reflection included?

Reflection provides a mechanism for identifying evidence gaps and
triggering re-planning rather than allowing the agent to stop after the
first plausible observation.

Why prevent duplicate tool calls?

Repeated identical calls increase cost and latency without necessarily
increasing information.

What state is persisted?

Investigation state includes the goal, service context, observations,
tool calls, hypotheses, evidence, iteration information, termination
information and approval-related state.

What does LangGraph provide?

LangGraph provides a structured graph/state-machine abstraction for
representing agent transitions and stateful execution rather than
manually wiring every transition.

When is human approval required?

When the next action crosses from investigation/recommendation into a
potentially impactful operational change.

🏁 Project Status

                 OpsPilot
                    │
       ┌────────────┼────────────┐
       │            │            │
       ▼            ▼            ▼
    Agent         RAG        Evaluation
    Logic       Grounding      30/30
       │            │            │
       ├────────────┼────────────┤
       │            │            │
       ▼            ▼            ▼
   LangGraph    Reflection   Observability
       │            │            │
       └────────────┼────────────┘
                    │
                    ▼
              FastAPI + UI
                    │
                    ▼
                 Docker

Current state

[✓] Agent investigation loop
[✓] Tool execution
[✓] Hypothesis generation
[✓] Evidence verification
[✓] Reflection / re-planning
[✓] RAG
[✓] Guardrails
[✓] Human approval boundary
[✓] LangGraph integration
[✓] Trajectory logging
[✓] Trajectory viewer
[✓] FastAPI
[✓] Streamlit UI
[✓] Docker packaging
[✓] 30 unique evaluation scenarios
[✓] Automated evaluation
[✓] Failure-analysis artifact
[✓] GitHub repository
[ ] Final five-minute demo video
[ ] Reflection ON/OFF ablation experiment

🎥 Demo Plan

A strong five-minute demonstration can follow this sequence:

00:00 – 00:30
Show repository + architecture

00:30 – 01:30
Explain the incident-investigation problem

01:30 – 03:00
Run a live checkout-api investigation

03:00 – 03:45
Show trajectory viewer / agent iterations

03:45 – 04:30
Show evaluation results

04:30 – 05:00
Show Docker + FastAPI + human approval boundary

The goal is not to spend five minutes showing code.

The goal is to demonstrate:

Goal
 ↓
Autonomous investigation
 ↓
Evidence
 ↓
Reasoning state
 ↓
Verification
 ↓
Report
 ↓
Safety boundary

📦 Submission Checklist

GitHub repository                         ✓
Clean project structure                  ✓
Meaningful source organization           ✓
Architecture description                 ✓
Professional README                     ✓
Docker packaging                         ✓
30+ evaluation scenarios                 ✓
Automated evaluation pipeline            ✓
Metric summary                           ✓
Failure-analysis report                  ✓
Trajectory viewer                        ✓
FastAPI integration                      ✓
Streamlit UI                             ✓
Human approval boundary                  ✓
Observability / trajectories             ✓
Five-minute demo                         ☐
Reflection ON/OFF comparison             ☐

🚀 Where OpsPilot Can Go Next

The current system is a production-oriented prototype, not a production
incident platform.

Natural extensions include:

Real Prometheus / Grafana integration
Real Kubernetes deployment data
Real log aggregation
Adaptive reflection cadence
Multi-service dependency graphs
More independent evidence requirements
Better duplicate-call suppression
Human feedback incorporated into hypotheses
Persistent investigation memory
Distributed tracing integration
Automated rollback workflows behind approval
Online evaluation and regression detection

The architectural foundation is intentionally designed so these
capabilities can be added without turning the controller into a single
monolithic prompt.

📌 Limitations

OpsPilot should currently be understood as a controlled prototype.

Important limitations include:

The benchmark uses controlled/synthetic incident data rather than a
live production environment.

Operational tools are simulated/local rather than connected to a
real Prometheus, log aggregation platform, Kubernetes cluster or
production deployment system.

The current benchmark contains 30 scenarios; a larger and more
adversarial evaluation suite would provide stronger evidence of
generalization.

The reported benchmark metrics should not be interpreted as
production reliability guarantees.

Average evidence count is currently 1.0, so stronger multi-source
evidence requirements are a useful future improvement.

Average unnecessary tool calls are currently 1.0, leaving room for
better investigation efficiency.

The reflection ON/OFF ablation should be measured explicitly before
making claims about reflection's quantitative benefit.

High-impact actions are protected by human approval rather than
fully autonomous execution.

🧭 The Core Idea

OpsPilot is ultimately built around one principle:

An incident investigation agent should not merely produce an answer.
It should produce a defensible investigation.

That means:

             ANSWER
               ▲
               │
          ┌────┴────┐
          │ REPORT  │
          └────┬────┘
               │
          VERIFIED
          EVIDENCE
               ▲
               │
        ┌──────┴──────┐
        │ HYPOTHESES  │
        └──────┬──────┘
               │
        OBSERVATIONS
               ▲
               │
        ┌──────┴──────┐
        │    TOOLS    │
        └──────┬──────┘
               │
             PLAN
               ▲
               │
             GOAL

The final report is only the top of the pyramid.

The real system is everything underneath it.

🔗 Repository

OpsPilot:
https://github.com/deepshikapalepu20/opspilot

👩‍💻 Project

OpsPilot --- Autonomous Incident Investigation Agent

A focused exploration of agentic AI for:

incident investigation

tool-using agents

evidence-grounded reasoning

RAG

reflection

stateful planning

human-in-the-loop safety

trajectory observability

agent evaluation

reproducible deployment

<p align="center">

Investigate with evidence.
Reason with state.
Reflect when uncertain.
Act only within safe boundaries.

</p>