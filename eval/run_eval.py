import json
from pathlib import Path

from opspilot.agent_loop import run_investigation


# ============================================================
# FILE PATHS
# ============================================================

SCENARIOS_PATH = Path("eval/scenarios.json")
RESULTS_PATH = Path("eval/results.json")
SUMMARY_PATH = Path("eval/summary.json")
FAILURE_PATH = Path("eval/failure_analysis.md")


# ============================================================
# HELPERS
# ============================================================

def extract_tool_names(state: dict) -> list[str]:
    """
    Extract tool names from the dictionary-based AgentState.
    """

    tool_calls = state.get(
        "tool_calls",
        [],
    )

    tools_called = []

    for call in tool_calls:

        if not isinstance(call, dict):
            continue

        tool_name = call.get("tool")

        if tool_name:
            tools_called.append(tool_name)

    return tools_called


def calculate_tool_argument_accuracy(
    scenario: dict,
    state: dict,
) -> float:
    """
    Calculate tool argument accuracy.

    Expected arguments are defined per tool in the scenario:

        "expected_arguments": {
            "query_metrics": {
                "service": "checkout-api",
                "metric": "latency_ms_p95"
            }
        }

    Each expected key/value pair receives one point when
    the agent supplies the expected value.

    If a tool is called multiple times, the call with the
    highest argument match is used.

    This prevents retries or query reformulation from
    artificially increasing the denominator.
    """

    expected_arguments = scenario.get(
        "expected_arguments",
        {},
    )

    # Older scenarios without expected arguments are treated
    # as fully accurate for backward compatibility.
    if not expected_arguments:
        return 1.0

    tool_calls = state.get(
        "tool_calls",
        [],
    )

    if not isinstance(tool_calls, list):
        return 0.0

    total_expected_arguments = 0
    matched_arguments = 0

    for tool_name, expected_args in expected_arguments.items():

        if not isinstance(expected_args, dict):
            continue

        total_expected_arguments += len(
            expected_args
        )

        actual_calls = []

        for call in tool_calls:

            if not isinstance(call, dict):
                continue

            if call.get("tool") != tool_name:
                continue

            actual_args = call.get(
                "arguments",
                {},
            )

            if isinstance(actual_args, dict):
                actual_calls.append(
                    actual_args
                )

        # Tool was never called.
        if not actual_calls:
            continue

        # Find the actual invocation that best matches
        # the expected structured arguments.
        best_match = 0

        for actual_args in actual_calls:

            current_match = 0

            for key, expected_value in expected_args.items():

                if (
                    key in actual_args
                    and actual_args[key] == expected_value
                ):
                    current_match += 1

            best_match = max(
                best_match,
                current_match,
            )

        matched_arguments += best_match

    if total_expected_arguments == 0:
        return 1.0

    return round(
        matched_arguments
        / total_expected_arguments,
        2,
    )


def build_root_cause_text(state: dict) -> str:
    """
    Build the text used for root-cause evaluation.

    We evaluate:
        1. hypotheses
        2. final report
        3. controller evidence
        4. collected evidence

    This allows a scenario to be marked correct when the
    expected root-cause concept appears in the grounded
    investigation output.
    """

    hypotheses = state.get(
        "hypotheses",
        [],
    )

    report = state.get(
        "report",
        {},
    ) or {}

    controller_evidence = state.get(
        "controller_evidence",
        "",
    )

    evidence = state.get(
        "evidence",
        [],
    )

    return " ".join(
        [
            json.dumps(
                hypotheses,
                default=str,
            ),
            json.dumps(
                report,
                default=str,
            ),
            json.dumps(
                controller_evidence,
                default=str,
            ),
            json.dumps(
                evidence,
                default=str,
            ),
        ]
    ).lower()


# ============================================================
# SCORE ONE SCENARIO
# ============================================================

def score_scenario(
    scenario: dict,
    state: dict,
) -> dict:
    """
    Score one evaluation scenario against the actual
    dictionary-based AgentState returned by OpsPilot.
    """

    # --------------------------------------------------------
    # TOOL CALLS
    # --------------------------------------------------------

    tools_called = extract_tool_names(
        state
    )

    tool_set = set(
        tools_called
    )

    expected_tools = scenario.get(
        "expected_tools",
        [],
    )

    expected_set = set(
        expected_tools
    )

    # --------------------------------------------------------
    # TOOL SELECTION ACCURACY
    # --------------------------------------------------------

    if expected_set:

        matched_tools = (
            tool_set & expected_set
        )

        tool_selection_accuracy = (
            len(matched_tools)
            / len(expected_set)
        )

    else:

        tool_selection_accuracy = 1.0

    # --------------------------------------------------------
    # TOOL ARGUMENT ACCURACY
    # --------------------------------------------------------

    tool_argument_accuracy = (
        calculate_tool_argument_accuracy(
            scenario,
            state,
        )
    )

    # --------------------------------------------------------
    # UNNECESSARY TOOL CALLS
    # --------------------------------------------------------

    unnecessary_tool_calls = len(
        tool_set - expected_set
    )

    # --------------------------------------------------------
    # ROOT CAUSE ACCURACY
    # --------------------------------------------------------

    root_cause_text = (
        build_root_cause_text(
            state
        )
    )

    expected_keywords = scenario.get(
        "expected_root_cause_keywords",
        [],
    )

    # Backward compatibility in case an older scenario file
    # still contains the singular field.
    if not expected_keywords:

        legacy_keyword = scenario.get(
            "expected_root_cause_keyword",
            "",
        )

        if legacy_keyword:
            expected_keywords = [
                legacy_keyword
            ]

    expected_keywords = [
        str(keyword).strip().lower()
        for keyword in expected_keywords
        if keyword
    ]

    # A scenario is currently considered root-cause correct
    # when at least one acceptable concept appears in the
    # grounded investigation output.
    root_cause_correct = any(
        keyword in root_cause_text
        for keyword in expected_keywords
    )

    # --------------------------------------------------------
    # INVESTIGATION COMPLETION
    # --------------------------------------------------------

    terminated = bool(
        state.get(
            "terminated",
            False,
        )
    )

    termination_reason = state.get(
        "termination_reason",
        "unknown",
    )

    investigation_completed = (
        terminated
    )

    # A clean investigation should either:
    #
    #   reported
    #       -> final report generated
    #
    #   awaiting_human_approval
    #       -> investigation completed but action is gated
    #
    loop_completed_cleanly = (
        termination_reason
        in {
            "reported",
            "awaiting_human_approval",
        }
    )

    # --------------------------------------------------------
    # APPROVAL
    # --------------------------------------------------------

    report = state.get(
        "report",
        {},
    ) or {}

    approval_actual = (
        termination_reason
        == "awaiting_human_approval"
        or bool(
            report.get(
                "requires_approval",
                False,
            )
        )
    )

    approval_expected = bool(
        scenario.get(
            "requires_approval_expected",
            False,
        )
    )

    approval_gating_correct = (
        approval_expected
        == approval_actual
    )

    # --------------------------------------------------------
    # EVIDENCE / GROUNDING
    # --------------------------------------------------------

    evidence = state.get(
        "evidence",
        [],
    )

    controller_grounded = bool(
        state.get(
            "controller_grounded",
            False,
        )
    )

    evidence_count = (
        len(evidence)
        if isinstance(
            evidence,
            list,
        )
        else 0
    )

    # --------------------------------------------------------
    # RESULT OBJECT
    # --------------------------------------------------------

    return {
        "scenario_id": scenario.get(
            "scenario_id"
        ),

        "pattern": scenario.get(
            "pattern"
        ),

        "goal": scenario.get(
            "goal"
        ),

        "expected_root_cause_keywords": (
            scenario.get(
                "expected_root_cause_keywords",
                [],
            )
        ),

        "expected_tools": (
            expected_tools
        ),

        "expected_arguments": (
            scenario.get(
                "expected_arguments",
                {},
            )
        ),

        "tools_called": (
            tools_called
        ),

        "tool_selection_accuracy": round(
            tool_selection_accuracy,
            2,
        ),

        "tool_argument_accuracy": (
            tool_argument_accuracy
        ),

        "unnecessary_tool_calls": (
            unnecessary_tool_calls
        ),

        "tool_calls_total": (
            len(tools_called)
        ),

        "investigation_completed": (
            investigation_completed
        ),

        "root_cause_correct": (
            root_cause_correct
        ),

        "loop_completed_cleanly": (
            loop_completed_cleanly
        ),

        "termination_reason": (
            termination_reason
        ),

        "requires_approval_expected": (
            approval_expected
        ),

        "requires_approval_actual": (
            approval_actual
        ),

        "approval_gating_correct": (
            approval_gating_correct
        ),

        "controller_grounded": (
            controller_grounded
        ),

        "evidence_count": (
            evidence_count
        ),

        "iterations": state.get(
            "iteration",
            0,
        ),
    }


# ============================================================
# RUN ALL SCENARIOS
# ============================================================

def run_all(
    scenarios_path=SCENARIOS_PATH,
):
    """
    Run the complete evaluation suite.
    """

    scenarios = json.loads(
        Path(
            scenarios_path
        ).read_text(
            encoding="utf-8"
        )
    )

    results = []

    total = len(
        scenarios
    )

    print()
    print("=" * 70)
    print(
        f"OPSPILOT EVALUATION — "
        f"{total} SCENARIOS"
    )
    print("=" * 70)

    for index, scenario in enumerate(
        scenarios,
        start=1,
    ):

        scenario_id = scenario.get(
            "scenario_id",
            f"SCN-{index:03d}",
        )

        goal = scenario.get(
            "goal",
            "",
        )

        print()
        print(
            f"[{index}/{total}] "
            f"{scenario_id}: "
            f"{goal}"
        )

        try:

            state = run_investigation(
                goal,
                max_iterations=10,
                service=scenario.get("service"),
            )

            result = score_scenario(
                scenario,
                state,
            )

            results.append(
                result
            )

            print(
                "  Root cause:",
                result[
                    "root_cause_correct"
                ],
            )

            print(
                "  Tool selection accuracy:",
                result[
                    "tool_selection_accuracy"
                ],
            )

            print(
                "  Tool argument accuracy:",
                result[
                    "tool_argument_accuracy"
                ],
            )

            print(
                "  Completed:",
                result[
                    "investigation_completed"
                ],
            )

            print(
                "  Clean loop:",
                result[
                    "loop_completed_cleanly"
                ],
            )

            print(
                "  Approval correct:",
                result[
                    "approval_gating_correct"
                ],
            )

            print(
                "  Grounded:",
                result[
                    "controller_grounded"
                ],
            )

            print(
                "  Termination:",
                result[
                    "termination_reason"
                ],
            )

            print(
                "  Tools:",
                result[
                    "tools_called"
                ],
            )

        except Exception as exc:

            print(
                "  ERROR:",
                repr(exc),
            )

            results.append(
                {
                    "scenario_id": scenario_id,

                    "pattern": scenario.get(
                        "pattern"
                    ),

                    "goal": goal,

                    "expected_root_cause_keywords": (
                        scenario.get(
                            "expected_root_cause_keywords",
                            [],
                        )
                    ),

                    "expected_tools": scenario.get(
                        "expected_tools",
                        [],
                    ),

                    "expected_arguments": (
                        scenario.get(
                            "expected_arguments",
                            {},
                        )
                    ),

                    "tools_called": [],

                    "tool_selection_accuracy": 0.0,

                    "tool_argument_accuracy": 0.0,

                    "unnecessary_tool_calls": 0,

                    "tool_calls_total": 0,

                    "investigation_completed": False,

                    "root_cause_correct": False,

                    "loop_completed_cleanly": False,

                    "termination_reason": (
                        f"evaluation_error: "
                        f"{exc}"
                    ),

                    "requires_approval_expected": (
                        scenario.get(
                            "requires_approval_expected",
                            False,
                        )
                    ),

                    "requires_approval_actual": False,

                    "approval_gating_correct": False,

                    "controller_grounded": False,

                    "evidence_count": 0,

                    "iterations": 0,
                }
            )

    return results


# ============================================================
# SUMMARY METRICS
# ============================================================

def summarize(
    results: list[dict],
) -> dict:

    n = len(
        results
    )

    if n == 0:

        return {
            "n_scenarios": 0,
        }

    return {
        # ----------------------------------------------------
        # Number of scenarios
        # ----------------------------------------------------

        "n_scenarios": n,

        # ----------------------------------------------------
        # Tool selection
        # ----------------------------------------------------

        "avg_tool_selection_accuracy": round(
            sum(
                r[
                    "tool_selection_accuracy"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Tool argument accuracy
        # ----------------------------------------------------

        "avg_tool_argument_accuracy": round(
            sum(
                r[
                    "tool_argument_accuracy"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Investigation completion
        # ----------------------------------------------------

        "investigation_success_rate": round(
            sum(
                r[
                    "investigation_completed"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Root cause
        # ----------------------------------------------------

        "root_cause_accuracy": round(
            sum(
                r[
                    "root_cause_correct"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Efficiency
        # ----------------------------------------------------

        "avg_tool_calls": round(
            sum(
                r[
                    "tool_calls_total"
                ]
                for r in results
            )
            / n,
            2,
        ),

        "avg_unnecessary_tool_calls": round(
            sum(
                r[
                    "unnecessary_tool_calls"
                ]
                for r in results
            )
            / n,
            2,
        ),

        # ----------------------------------------------------
        # Loop completion
        # ----------------------------------------------------

        "loop_completion_rate": round(
            sum(
                r[
                    "loop_completed_cleanly"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Approval gating
        # ----------------------------------------------------

        "approval_gating_correct_rate": round(
            sum(
                r[
                    "approval_gating_correct"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Controller grounding
        # ----------------------------------------------------

        "controller_grounding_rate": round(
            sum(
                r[
                    "controller_grounded"
                ]
                for r in results
            )
            / n,
            3,
        ),

        # ----------------------------------------------------
        # Evidence
        # ----------------------------------------------------

        "avg_evidence_count": round(
            sum(
                r[
                    "evidence_count"
                ]
                for r in results
            )
            / n,
            2,
        ),
    }


# ============================================================
# FAILURE ANALYSIS
# ============================================================

def write_failure_analysis(
    results: list[dict],
    out_path=FAILURE_PATH,
):

    failures = [
        result
        for result in results
        if (
            not result[
                "root_cause_correct"
            ]
            or not result[
                "loop_completed_cleanly"
            ]
            or not result[
                "approval_gating_correct"
            ]
            or result[
                "tool_argument_accuracy"
            ] < 1.0
        )
    ]

    lines = [
        "# OpsPilot — Failure Analysis",
        "",
        (
            "This report contains representative "
            "failures identified during the automated "
            "evaluation."
        ),
        "",
        f"Total scenarios: {len(results)}",
        f"Failures detected: {len(failures)}",
        "",
    ]

    if not failures:

        lines.extend(
            [
                "## Result",
                "",
                (
                    "No automated failures were detected "
                    "by the evaluation criteria."
                ),
                "",
                (
                    "Several trajectories should still "
                    "be reviewed manually before final "
                    "submission."
                ),
                "",
            ]
        )

    else:

        for failure in failures:

            lines.extend(
                [
                    (
                        f"## {failure['scenario_id']} "
                        f"— {failure['pattern']}"
                    ),
                    "",

                    (
                        f"**Goal:** "
                        f"{failure['goal']}"
                    ),
                    "",

                    (
                        f"**Expected root-cause keywords:** "
                        f"{failure['expected_root_cause_keywords']}"
                    ),
                    "",

                    (
                        f"**Root cause correct:** "
                        f"{failure['root_cause_correct']}"
                    ),
                    "",

                    (
                        f"**Tool selection accuracy:** "
                        f"{failure['tool_selection_accuracy']}"
                    ),
                    "",

                    (
                        f"**Tool argument accuracy:** "
                        f"{failure['tool_argument_accuracy']}"
                    ),
                    "",

                    (
                        f"**Expected arguments:** "
                        f"{failure['expected_arguments']}"
                    ),
                    "",

                    (
                        f"**Investigation completed:** "
                        f"{failure['investigation_completed']}"
                    ),
                    "",

                    (
                        f"**Termination:** "
                        f"{failure['termination_reason']}"
                    ),
                    "",

                    (
                        f"**Tools used:** "
                        f"{failure['tools_called']}"
                    ),
                    "",

                    (
                        f"**Tool calls:** "
                        f"{failure['tool_calls_total']}"
                    ),
                    "",

                    (
                        f"**Unnecessary calls:** "
                        f"{failure['unnecessary_tool_calls']}"
                    ),
                    "",

                    (
                        f"**Controller grounded:** "
                        f"{failure['controller_grounded']}"
                    ),
                    "",

                    (
                        f"**Approval expected:** "
                        f"{failure['requires_approval_expected']}"
                    ),
                    "",

                    (
                        f"**Approval actual:** "
                        f"{failure['requires_approval_actual']}"
                    ),
                    "",

                    (
                        f"**Approval gating correct:** "
                        f"{failure['approval_gating_correct']}"
                    ),
                    "",

                    "### Proposed improvement",
                    "",

                    (
                        "Inspect the corresponding "
                        "trajectory under "
                        "`data/trajectories/` using the "
                        "trajectory viewer. Determine whether "
                        "the failure originated from tool "
                        "selection, tool argument extraction, "
                        "evidence retrieval, hypothesis "
                        "generation, verification, reflection, "
                        "approval gating, or termination."
                    ),
                    "",
                ]
            )

    Path(
        out_path
    ).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"{len(failures)}/{len(results)} "
        f"scenarios flagged -> "
        f"{out_path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    results = run_all()

    # --------------------------------------------------------
    # Save individual results
    # --------------------------------------------------------

    RESULTS_PATH.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Generate summary
    # --------------------------------------------------------

    summary = summarize(
        results
    )

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Generate failure analysis
    # --------------------------------------------------------

    write_failure_analysis(
        results
    )

    # --------------------------------------------------------
    # Print final summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "FINAL EVALUATION SUMMARY"
    )
    print("=" * 70)

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    print()

    print(
        f"Results saved to: "
        f"{RESULTS_PATH}"
    )

    print(
        f"Summary saved to: "
        f"{SUMMARY_PATH}"
    )

    print(
        f"Failure analysis saved to: "
        f"{FAILURE_PATH}"
    )


if __name__ == "__main__":
    main()