import json
from pathlib import Path

import streamlit as st


TRAJECTORY_DIR = Path("data/trajectories")


st.set_page_config(
    page_title="OpsPilot Trajectory Viewer",
    layout="wide",
)

st.title("OpsPilot — Trajectory Viewer")

TRAJECTORY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

files = sorted(
    TRAJECTORY_DIR.glob("*.jsonl"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)


if not files:
    st.warning(
        "No investigation trajectories found. "
        "Run an investigation first."
    )
    st.stop()


selected_file = st.selectbox(
    "Select investigation",
    files,
    format_func=lambda p: p.name,
)


events = []

with selected_file.open(
    "r",
    encoding="utf-8",
) as f:
    for line in f:
        line = line.strip()

        if line:
            events.append(json.loads(line))


st.subheader("Investigation")

final_state = next(
    (
        event
        for event in reversed(events)
        if event["type"] == "final_state"
    ),
    None,
)


if final_state:
    payload = final_state["payload"]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Iterations",
        payload.get("total_iterations", 0),
    )

    col2.metric(
        "Tool Calls",
        len(payload.get("tool_calls", [])),
    )

    col3.metric(
        "Termination",
        payload.get(
            "termination_reason",
            "unknown",
        ),
    )


st.divider()

st.subheader("Trajectory")

for index, event in enumerate(events):
    event_type = event.get("type", "unknown")
    iteration = event.get("iteration")

    label = f"{index + 1}. [{iteration}] {event_type}"

    with st.expander(label):
        st.json(event.get("payload", {}))