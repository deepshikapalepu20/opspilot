import streamlit as st
import requests


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OpsPilot",
    page_icon="🚨",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("OpsPilot")

st.subheader(
    "Agentic AI Incident Investigation"
)

st.write(
    "Enter an incident or investigation goal and OpsPilot "
    "will analyze the available operational evidence."
)


# ============================================================
# INVESTIGATION INPUT
# ============================================================

goal = st.text_area(
    "Investigation Goal",
    value="Investigate checkout-api latency spike",
    height=100
)


# ============================================================
# INVESTIGATE BUTTON
# ============================================================

if st.button(
    "Investigate",
    type="primary"
):

    if not goal.strip():

        st.warning(
            "Please enter an investigation goal."
        )

    else:

        with st.spinner(
            "OpsPilot is investigating..."
        ):

            try:

                response = requests.post(
                    "http://127.0.0.1:8000/investigate",
                    json={
                        "goal": goal
                    },
                    timeout=300
                )

                if response.status_code == 200:

                    result = response.json()

                    # Store result in Streamlit session
                    st.session_state["result"] = result

                    st.success(
                        "Investigation completed successfully!"
                    )

                else:

                    st.error(
                        f"API returned status code "
                        f"{response.status_code}"
                    )

                    st.code(
                        response.text
                    )

            except requests.exceptions.ConnectionError:

                st.error(
                    "Could not connect to the OpsPilot API. "
                    "Make sure the FastAPI server is running."
                )

            except requests.exceptions.Timeout:

                st.error(
                    "The investigation timed out. "
                    "Please check the FastAPI terminal."
                )

            except Exception as e:

                st.error(
                    f"Unexpected error: {e}"
                )


# ============================================================
# DISPLAY INVESTIGATION RESULT
# ============================================================

if "result" in st.session_state:

    result = st.session_state["result"]

    final_report = result.get(
        "final_report",
    ) or {}

    # ========================================================
    # INCIDENT SUMMARY
    # ========================================================

    st.subheader(
        "Incident Summary"
    )

    if final_report:

        col1, col2 = st.columns(2)

        with col1:

            st.markdown(
                "**Incident**"
            )

            st.write(
                final_report.get(
                    "incident_title",
                    "Unknown"
                )
            )

        with col2:

            st.markdown(
                "**Root Cause**"
            )

            st.write(
                final_report.get(
                    "likely_root_cause",
                    "Unknown"
                )
            )

        col3, col4 = st.columns(2)

        with col3:

            confidence = final_report.get(
                "confidence_pct",
                0
            )

            st.metric(
                "Confidence",
                f"{confidence}%"
            )

        with col4:

            st.markdown(
                "**Recommended Action**"
            )

            st.write(
                final_report.get(
                    "recommended_action",
                    "No action recommended"
                )
            )
    else:
        st.warning(
            "Investigation was inconclusive. "
            "OpsPilot did not obtain enough verified evidence "
            "to produce a grounded root-cause report."
        )

        st.write(
            f"Termination reason: "
            f"{result.get('termination_reason', 'unknown')}"
        )

        st.write(
            f"Incident status: "
            f"{result.get('incident_status', 'unknown')}"
        )
    # ========================================================
    # EVIDENCE
    # ========================================================
    
    st.subheader(
        "Evidence"
    )

    evidence = final_report.get(
        "evidence",
        []
    )

    if evidence:

        for item in evidence:

            st.markdown(
                f"- {item}"
            )

    else:

        st.info(
            "No evidence summary available."
        )

    # ========================================================
    # APPROVAL
    # ========================================================

    st.subheader(
        "Human Approval"
    )

    pending_approval = result.get(
        "pending_approval",
        {}
    )

    if pending_approval:

        st.warning(
            "Human approval is required before "
            "executing the recommended action."
        )

        col1, col2 = st.columns(2)

        with col1:

            st.markdown(
                f"**Action:** "
                f"{pending_approval.get('action', 'Unknown')}"
            )

            st.markdown(
                f"**Service:** "
                f"{pending_approval.get('service', 'Unknown')}"
            )

        with col2:

            st.markdown(
                f"**Deployment:** "
                f"{pending_approval.get('deployment_id', 'Unknown')}"
            )

            st.markdown(
                f"**Status:** "
                f"{pending_approval.get('status', 'Unknown')}"
            )

        col1, col2 = st.columns(2)

        # ----------------------------------------------------
        # APPROVE
        # ----------------------------------------------------

        with col1:

            if st.button(
                "Approve Action",
                type="primary"
            ):

                with st.spinner(
                    "Executing approved action..."
                ):

                    try:

                        approval_response = requests.post(
                            "http://127.0.0.1:8000/approve",
                            json={
                                "approved": True
                            },
                            timeout=300
                        )

                        if (
                            approval_response.status_code
                            == 200
                        ):

                            approval_result = (
                                approval_response.json()
                            )

                            st.session_state[
                                "approval_result"
                            ] = approval_result

                            st.success(
                                "Action approved by operator."
                            )

                        else:

                            st.error(
                                "Approval request failed."
                            )

                            st.code(
                                approval_response.text
                            )

                    except Exception as e:

                        st.error(
                            f"Approval error: {e}"
                        )

        # ----------------------------------------------------
        # REJECT
        # ----------------------------------------------------

        with col2:

            if st.button(
                "Reject Action"
            ):

                try:

                    rejection_response = requests.post(
                        "http://127.0.0.1:8000/approve",
                        json={
                            "approved": False
                        },
                        timeout=300
                    )

                    if (
                        rejection_response.status_code
                        == 200
                    ):

                        rejection_result = (
                            rejection_response.json()
                        )

                        st.session_state[
                            "approval_result"
                        ] = rejection_result

                        st.warning(
                            "Action rejected by operator."
                        )

                    else:

                        st.error(
                            "Rejection request failed."
                        )

                except Exception as e:

                    st.error(
                        f"Rejection error: {e}"
                    )


    # ========================================================
    # APPROVAL RESULT
    # ========================================================

    if "approval_result" in st.session_state:

        approval_result = (
            st.session_state[
                "approval_result"
            ]
        )

        # ====================================================
        # ACTION EXECUTION
        # ====================================================

        action_execution = (
            approval_result.get(
                "action_execution"
            )
        )

        if action_execution:

            st.subheader(
                "Action Execution"
            )

            execution_status = (
                action_execution.get(
                    "status",
                    "unknown"
                )
            )

            st.write(
                f"**Status:** {execution_status}"
            )

            if action_execution.get(
                "action"
            ):

                st.write(
                    f"**Action:** "
                    f"{action_execution.get('action')}"
                )

            if action_execution.get(
                "service"
            ):

                st.write(
                    f"**Service:** "
                    f"{action_execution.get('service')}"
                )

            if action_execution.get(
                "deployment_id"
            ):

                st.write(
                    f"**Deployment:** "
                    f"{action_execution.get('deployment_id')}"
                )

            message = action_execution.get(
                "message"
            )

            if message:

                if execution_status == "executed":

                    st.success(
                        message
                    )

                elif execution_status == "rejected":

                    st.warning(
                        message
                    )

                else:

                    st.error(
                        message
                    )

        # ====================================================
        # POST-ACTION VERIFICATION
        # ====================================================

        verification = (
            approval_result.get(
                "verification_result"
            )
        )

        if verification:

            st.subheader(
                "Post-Action Verification"
            )

            verification_status = (
                verification.get(
                    "status",
                    "unknown"
                )
            )

            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            if verification_status == "resolved":

                st.success(
                    "Incident resolved successfully."
                )

            elif (
                verification_status
                == "not_resolved"
            ):

                st.error(
                    "Incident is not fully resolved. "
                    "Further investigation is required."
                )

            else:

                st.warning(
                    "Insufficient data to verify "
                    "incident resolution."
                )

            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            col1, col2, col3 = st.columns(3)

            with col1:

                before = verification.get(
                    "before_average"
                )

                if before is not None:

                    st.metric(
                        "Latency Before",
                        f"{before} ms"
                    )

            with col2:

                after = verification.get(
                    "after_average"
                )

                if after is not None:

                    st.metric(
                        "Latency After",
                        f"{after} ms"
                    )

            with col3:

                improvement = verification.get(
                    "improvement_pct"
                )

                if improvement is not None:

                    st.metric(
                        "Improvement",
                        f"{improvement}%"
                    )

            # ------------------------------------------------
            # ERROR STATUS
            # ------------------------------------------------

            st.write(
                f"**Errors Remaining:** "
                f"{verification.get('after_error_count', 0)}"
            )

            st.write(
                f"**Latency Improved:** "
                f"{verification.get('latency_improved', False)}"
            )

            st.write(
                f"**Incident Status:** "
                f"{approval_result.get('incident_status', 'unknown')}"
            )

            st.info(
                verification.get(
                    "message",
                    "No verification message available."
                )
            )


    # ========================================================
    # AGENT REFLECTION
    # ========================================================

    reflection = result.get(
        "reflection",
        {}
    )

    if reflection:

        st.subheader(
            "Agent Reflection"
        )

        selected = reflection.get(
            "selected_hypothesis",
            {}
        )

        if selected:

            st.write(
                f"**Selected Hypothesis:** "
                f"{selected.get('cause', 'Unknown')}"
            )

            st.write(
                f"**Confidence:** "
                f"{selected.get('confidence', 0)}%"
            )

            st.write(
                f"**Reason:** "
                f"{selected.get('reason', 'Not provided')}"
            )

        st.write(
            f"**Continue Investigation:** "
            f"{reflection.get('continue_investigation', False)}"
        )


    # ========================================================
    # AI ANALYSIS
    # ========================================================

    llm_analysis = final_report.get(
        "llm_analysis"
    )

    if llm_analysis:

        st.subheader(
            "AI Incident Analysis"
        )

        st.markdown(
            llm_analysis
        )


    # ========================================================
    # TECHNICAL STATE
    # ========================================================

    with st.expander(
        "View Technical Investigation State"
    ):

        st.json(
            result
        )