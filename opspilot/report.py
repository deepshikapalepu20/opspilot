from typing import Any

from .llm import generate_response


# ============================================================
# HELPERS
# ============================================================

def _safe_confidence(value: Any) -> int:
    """
    Normalize confidence to an integer percentage.
    """

    try:
        confidence = int(float(value))
    except (TypeError, ValueError):
        return 0

    return max(
        0,
        min(
            100,
            confidence,
        ),
    )


def _get_selected_hypothesis(
    state: dict[str, Any],
) -> tuple[str, int]:
    """
    Get the selected hypothesis from the actual AgentState.

    IMPORTANT:
    agent_loop.py stores this as:

        state["selected_hypothesis"]

    It is NOT stored inside reflection.
    """

    selected = state.get(
        "selected_hypothesis"
    )

    # --------------------------------------------------------
    # New/current agent_loop format
    # --------------------------------------------------------

    if isinstance(
        selected,
        str,
    ) and selected.strip():

        confidence = 0

        # Try to obtain confidence from the matching
        # hypothesis.
        for hypothesis in state.get(
            "hypotheses",
            [],
        ):

            if not isinstance(
                hypothesis,
                dict,
            ):
                continue

            cause = hypothesis.get(
                "cause"
            )

            if (
                isinstance(
                    cause,
                    str,
                )
                and cause.strip()
                == selected.strip()
            ):

                confidence = _safe_confidence(
                    hypothesis.get(
                        "confidence_pct",
                        hypothesis.get(
                            "confidence",
                            0,
                        ),
                    )
                )

                break

        return (
            selected.strip(),
            confidence,
        )

    # --------------------------------------------------------
    # Evidence-grounded controller hypothesis
    # --------------------------------------------------------

    evidence_grounded = state.get(
        "evidence_grounded_hypothesis"
    )

    if evidence_grounded and isinstance(
        selected,
        str,
    ):

        return (
            selected.strip(),
            80,
        )

    # --------------------------------------------------------
    # Backward compatibility with older reflection format
    # --------------------------------------------------------

    reflection = state.get(
        "reflection",
        {},
    )

    if isinstance(
        reflection,
        dict,
    ):

        reflection_selected = reflection.get(
            "selected_hypothesis"
        )

        if isinstance(
            reflection_selected,
            dict,
        ):

            cause = reflection_selected.get(
                "cause",
                "Unknown root cause",
            )

            confidence = _safe_confidence(
                reflection_selected.get(
                    "confidence",
                    reflection_selected.get(
                        "confidence_pct",
                        0,
                    ),
                )
            )

            return (
                cause,
                confidence,
            )

        if isinstance(
            reflection_selected,
            str,
        ) and reflection_selected.strip():

            return (
                reflection_selected.strip(),
                0,
            )

    return (
        "Unknown root cause",
        0,
    )


def _collect_evidence_summary(
    state: dict[str, Any],
) -> list[str]:
    """
    Build evidence directly from actual tool observations
    whenever possible.

    This prevents the final report from depending only on
    LLM-generated evidence descriptions.
    """

    summary: list[str] = []

    # ========================================================
    # ACTUAL TOOL RESULTS
    # ========================================================

    for observation in state.get(
        "observations",
        [],
    ):

        if not isinstance(
            observation,
            dict,
        ):
            continue

        source = observation.get(
            "source",
            "unknown",
        )

        data = observation.get(
            "data"
        )

        if not data:
            continue

        # ----------------------------------------------------
        # LOGS
        # ----------------------------------------------------

        if source == "search_logs":

            if not isinstance(
                data,
                dict,
            ):
                continue

            logs = data.get(
                "logs",
                [],
            )

            if not isinstance(
                logs,
                list,
            ):
                continue

            for log in logs:

                if not isinstance(
                    log,
                    dict,
                ):
                    continue

                timestamp = log.get(
                    "t",
                    "unknown time",
                )

                level = log.get(
                    "level",
                    "UNKNOWN",
                )

                service = log.get(
                    "service",
                    "",
                )

                message = log.get(
                    "message",
                    "",
                )

                if message:

                    service_text = (
                        f" [{service}]"
                        if service
                        else ""
                    )

                    summary.append(
                        f"{timestamp}{service_text} "
                        f"{level}: {message}"
                    )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        elif source == "query_metrics":

            if not isinstance(
                data,
                dict,
            ):
                continue

            metric = data.get(
                "metric",
                "metric",
            )

            points = data.get(
                "points",
                [],
            )

            if not isinstance(
                points,
                list,
            ):
                continue

            formatted_points = []

            for point in points:

                if not isinstance(
                    point,
                    dict,
                ):
                    continue

                timestamp = point.get(
                    "t"
                )

                value = point.get(
                    "v"
                )

                if (
                    timestamp is not None
                    and value is not None
                ):

                    formatted_points.append(
                        f"{timestamp}={value}"
                    )

            if formatted_points:

                summary.append(
                    f"{metric}: "
                    + ", ".join(
                        formatted_points
                    )
                )

        # ----------------------------------------------------
        # DEPLOYMENTS
        # ----------------------------------------------------

        elif source == "get_deployments":

            if not isinstance(
                data,
                dict,
            ):
                continue

            deployments = data.get(
                "deployments",
                [],
            )

            if not isinstance(
                deployments,
                list,
            ):
                continue

            for deployment in deployments:

                if not isinstance(
                    deployment,
                    dict,
                ):
                    continue

                deployment_id = deployment.get(
                    "deployment_id",
                    "unknown deployment",
                )

                deployed_at = deployment.get(
                    "deployed_at",
                    "unknown time",
                )

                service = deployment.get(
                    "service",
                    "",
                )

                changes = deployment.get(
                    "changes",
                    [],
                )

                if isinstance(
                    changes,
                    list,
                ):

                    changes_text = (
                        "; ".join(
                            str(change)
                            for change in changes
                        )
                    )

                else:

                    changes_text = str(
                        changes
                    )

                summary.append(
                    f"Deployment {deployment_id} "
                    f"for {service} at {deployed_at}: "
                    f"{changes_text}"
                )

        # ----------------------------------------------------
        # OTHER TOOLS
        # ----------------------------------------------------

        else:

            summary.append(
                f"{source}: {data}"
            )

    # ========================================================
    # FALLBACK TO EVIDENCE OBJECTS
    # ========================================================

    if not summary:

        for item in state.get(
            "evidence",
            [],
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            hypothesis = item.get(
                "hypothesis"
            )

            supporting = item.get(
                "supporting_evidence",
                [],
            )

            if not isinstance(
                supporting,
                list,
            ):

                supporting = [
                    str(supporting)
                ]

            if hypothesis:

                summary.append(
                    f"{hypothesis}: "
                    + "; ".join(
                        str(value)
                        for value in supporting
                    )
                )

    return summary


# ============================================================
# RAG KNOWLEDGE RETRIEVAL
# ============================================================

def _retrieve_rag_context(
    state: dict[str, Any],
    root_cause: str,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant operational knowledge for the final
    incident analysis.

    RAG knowledge is contextual information only. It does not
    override live operational evidence or establish causation
    by itself.
    """

    goal = state.get(
        "goal",
        "",
    )

    service = state.get(
        "service"
    )

    if not service:

        service = state.get(
            "affected_service"
        )

    query_parts = []

    if goal:
        query_parts.append(
            str(goal)
        )

    if root_cause:
        query_parts.append(
            f"root cause context: {root_cause}"
        )

    query = " ".join(
        query_parts
    ).strip()

    if not query:
        return []

    try:

        from opspilot.rag.retriever import retrieve

        result = retrieve(
            query=query,
            service=service,
        )

    except Exception as exc:

        print(
            "\n=== RAG REPORT RETRIEVAL ERROR ==="
        )

        print(
            str(exc)
        )

        return []

    chunks = result.get(
        "chunks",
        [],
    )

    if not isinstance(
        chunks,
        list,
    ):
        return []

    normalized = []

    for chunk in chunks:

        if not isinstance(
            chunk,
            dict,
        ):
            continue

        text = chunk.get(
            "text",
            "",
        )

        source = chunk.get(
            "source",
            {},
        )

        distance = chunk.get(
            "distance"
        )

        if not isinstance(
            text,
            str,
        ) or not text.strip():

            continue

        normalized.append(
            {
                "text": text.strip(),
                "source": source,
                "distance": distance,
            }
        )

    return normalized


def _format_rag_context(
    rag_chunks: list[dict[str, Any]],
) -> str:
    """
    Convert retrieved RAG chunks into compact context for
    the final analysis LLM.
    """

    if not rag_chunks:
        return "No additional RAG knowledge was retrieved."

    formatted = []

    for index, chunk in enumerate(
        rag_chunks,
        start=1,
    ):

        source = chunk.get(
            "source",
            {},
        )

        if isinstance(
            source,
            dict,
        ):

            source_name = source.get(
                "source",
                source.get(
                    "document_id",
                    "unknown source",
                ),
            )

        else:

            source_name = str(
                source
            )

        text = chunk.get(
            "text",
            "",
        )

        formatted.append(
            f"[RAG SOURCE {index}: {source_name}]\n"
            f"{text}"
        )

    return "\n\n".join(
        formatted
    )


def _build_grounded_analysis(
    state: dict[str, Any],
    root_cause: str,
    confidence: int,
    evidence_summary: list[str],
    rag_chunks: list[dict[str, Any]],
) -> str:
    """
    Build the context supplied to the LLM.

    The LLM is explicitly told not to replace the controller's
    root-cause determination with "unknown" when the evidence
    gate has already passed.

    RAG knowledge is supplied as contextual knowledge and must
    not be treated as current operational evidence.
    """

    incident_title = state.get(
        "goal",
        "Unknown incident",
    )

    observations = state.get(
        "observations",
        [],
    )

    rag_context = _format_rag_context(
        rag_chunks
    )

    context = {
        "incident": incident_title,
        "controller_selected_root_cause": root_cause,
        "controller_confidence_pct": confidence,
        "evidence_gate_passed": True,
        "evidence": evidence_summary,
        "rag_knowledge": rag_context,
        "observation_count": len(
            observations
        ),
    }

    prompt = f"""
You are an SRE incident investigation assistant.

The OpsPilot controller has already passed its evidence gate.

You MUST respect the controller's selected root cause.

Do NOT replace it with "Unknown root cause" unless the supplied
LIVE operational evidence directly contradicts it.

There are two different evidence classes in this context:

1. LIVE OPERATIONAL EVIDENCE
   - logs
   - metrics
   - deployments
   - current tool observations

2. RAG KNOWLEDGE
   - runbooks
   - troubleshooting documentation
   - architecture documentation
   - historical incidents

LIVE OPERATIONAL EVIDENCE is authoritative for determining
what happened in the current incident.

RAG KNOWLEDGE is contextual guidance only.

IMPORTANT RAG RULES:

- Do NOT treat a historical incident as proof that the same
  root cause occurred in the current incident.
- Do NOT treat a runbook statement as proof that a condition
  exists now.
- Do NOT invent current operational facts from RAG documents.
- Use RAG to explain investigation mechanisms and recommend
  evidence-preserving remediation steps.
- Clearly distinguish historical examples from current evidence.

Do NOT invent:
- logs
- metrics
- deployments
- database behavior
- network behavior
- user impact
- remediation results

Distinguish carefully between:

1. DIRECTLY OBSERVED FACTS
2. STRONGLY SUPPORTED ROOT CAUSE
3. LIKELY CONTRIBUTING FACTORS
4. CORRELATIONS THAT ARE NOT PROVEN CAUSATION
5. RAG-BASED INVESTIGATION OR REMEDIATION GUIDANCE

In particular, a deployment occurring before an incident is
correlation unless the live evidence explicitly proves
causation.

Investigation context:

{context}

Write a concise incident analysis with exactly these sections:

### 1. Root Cause
State the controller-selected root cause clearly.

Do not replace the selected root cause with a historical
incident from RAG.

If the evidence establishes the mechanism but only suggests
which deployment change contributed to it, say so explicitly.

### 2. Evidence
List the strongest concrete observations from the LIVE
operational tool results, including timestamps and values
where available.

Do NOT present RAG documentation as current operational
evidence.

### 3. Impact
Describe only impact supported by the LIVE evidence.

If user-facing impact is not directly available, say that
the evidence shows service degradation rather than inventing
customer impact.

### 4. Recommended Action
Use the RAG knowledge and the live evidence to recommend
specific, evidence-preserving, low-risk next steps.

You may use historical incidents and runbooks as guidance,
but clearly frame them as guidance rather than proof.

Do not claim that a rollback or production-changing action
has been executed.

Do not invent a successful remediation.

Return only the analysis.
"""

    try:
        return generate_response(
            prompt
        )

    except Exception as exc:

        # Deterministic fallback.
        return (
            "### 1. Root Cause\n"
            f"{root_cause}\n\n"
            "### 2. Evidence\n"
            + "\n".join(
                f"- {item}"
                for item in evidence_summary
            )
            + "\n\n"
            "### 3. Impact\n"
            "The evidence demonstrates service degradation "
            "during the investigated window. No unsupported "
            "user-impact claim is made.\n\n"
            "### 4. Recommended Action\n"
            "Review the retry behavior and connection-pool "
            "configuration, and collect direct pool-utilization "
            "and retry metrics before making production-changing "
            "changes.\n\n"
            f"LLM analysis unavailable: {exc}"
        )


# ============================================================
# MAIN REPORT CREATION
# ============================================================

def create_incident_report(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Create the final structured incident report from the
    investigation state.

    IMPORTANT:
    The structured report is controlled by the AgentState,
    not by an LLM-generated reflection object.
    """

    incident_title = state.get(
        "goal",
        "Unknown incident",
    )

    approval = state.get(
        "pending_approval"
    )

    # ========================================================
    # ROOT CAUSE
    # ========================================================

    likely_root_cause, confidence_pct = (
        _get_selected_hypothesis(
            state
        )
    )

    # ========================================================
    # EVIDENCE
    # ========================================================

    evidence_summary = (
        _collect_evidence_summary(
            state
        )
    )

    # ========================================================
    # FALLBACK EVIDENCE
    # ========================================================

    if not evidence_summary:

        evidence_summary = [
            "No usable evidence was collected."
        ]

    # ========================================================
    # RAG KNOWLEDGE
    # ========================================================

    rag_chunks = _retrieve_rag_context(
        state,
        likely_root_cause,
    )

    # ========================================================
    # RECOMMENDED ACTION
    # ========================================================

    if approval:

        action = approval.get(
            "action"
        )

        if action:

            recommended_action = (
                f"Pending approved action: {action}"
            )

        else:

            recommended_action = (
                "A high-impact action is pending approval."
            )

    else:

        recommended_action = (
            "Review the retry-wrapper behavior and "
            "connection-pool configuration. Collect direct "
            "connection-pool utilization, connection-wait, "
            "timeout, and retry metrics before making "
            "production-changing configuration changes."
        )

    # ========================================================
    # APPROVAL
    # ========================================================

    requires_approval = bool(
        approval
        and approval.get(
            "status"
        ) == "pending"
    )

    # ========================================================
    # EVIDENCE GATE STATUS
    # ========================================================

    evidence_gate_passed = (
        state.get(
            "termination_reason"
        )
        in {
            "evidence_sufficient",
            "reported",
        }
        or bool(
            state.get(
                "evidence_grounded_hypothesis"
            )
        )
    )

    # ========================================================
    # STRUCTURED CONTEXT
    # ========================================================

    investigation_context = {
        "incident": incident_title,
        "root_cause": likely_root_cause,
        "confidence_pct": confidence_pct,
        "evidence_gate_passed": evidence_gate_passed,
        "evidence": evidence_summary,
        "rag_knowledge": _format_rag_context(
            rag_chunks
        ),
        "recommended_action": recommended_action,
    }

    # ========================================================
    # LLM ANALYSIS
    # ========================================================

    if (
        evidence_gate_passed
        and likely_root_cause
        != "Unknown root cause"
    ):

        llm_analysis = _build_grounded_analysis(
            state,
            likely_root_cause,
            confidence_pct,
            evidence_summary,
            rag_chunks,
        )

    else:

        # This branch is for genuinely inconclusive cases.
        prompt = f"""
You are an SRE incident investigation assistant.

The investigation does NOT have sufficient verified evidence
to establish a root cause.

Investigation:

{investigation_context}

RAG knowledge is contextual guidance only. It must not be
used as proof of the current incident's root cause.

Write a concise explanation containing:

### 1. Root Cause
State that the root cause is inconclusive.

### 2. Evidence
List the evidence actually collected.

### 3. Impact
State only what is supported by the evidence.

### 4. Recommended Action
Recommend additional read-only investigation, using RAG
knowledge only as supplementary guidance.

Do not invent facts.
"""

        try:

            llm_analysis = generate_response(
                prompt
            )

        except Exception as exc:

            llm_analysis = (
                "### 1. Root Cause\n"
                "Inconclusive.\n\n"
                "### 2. Evidence\n"
                + "\n".join(
                    f"- {item}"
                    for item in evidence_summary
                )
                + "\n\n"
                "### 3. Impact\n"
                "Insufficient evidence for a stronger impact "
                "assessment.\n\n"
                "### 4. Recommended Action\n"
                "Continue read-only evidence collection.\n\n"
                f"LLM analysis unavailable: {exc}"
            )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "incident_title": incident_title,
        "likely_root_cause": likely_root_cause,
        "confidence_pct": confidence_pct,
        "evidence": evidence_summary,
        "rag_knowledge": rag_chunks,
        "recommended_action": recommended_action,
        "requires_approval": requires_approval,
        "llm_analysis": llm_analysis,
    }


# ============================================================
# REPORT NODE
# ============================================================

def report_node(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate and store the final incident report.
    """

    report = create_incident_report(
        state
    )

    return {
        "final_report": report
    }