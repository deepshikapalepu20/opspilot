import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOG_DIR = Path("data/trajectories")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _json_safe(value: Any) -> Any:
    """
    Convert common Python objects into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): _json_safe(val)
            for key, val in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())

    if hasattr(value, "dict"):
        return _json_safe(value.dict())

    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))

    return str(value)


class Tracer:
    """
    Records an OpsPilot investigation trajectory.

    Each investigation is stored as a JSONL file under:

        data/trajectories/

    Events include:
        - plan_created
        - tool_request
        - tool_result
        - tool_error
        - reflection
        - replanned
        - final_state
    """

    def __init__(
        self,
        investigation_id: str | None = None,
    ):
        self.id = investigation_id or str(uuid.uuid4())[:8]

        safe_id = "".join(
            char
            if char.isalnum() or char in "-_"
            else "_"
            for char in self.id
        )

        self.path = (
            LOG_DIR / f"{safe_id}.jsonl"
        )

        self.events: list[dict[str, Any]] = []

    def log(
        self,
        event_type: str,
        payload: dict[str, Any],
        iteration: int | None = None,
    ) -> None:
        """
        Record one trajectory event.
        """

        event = {
            "timestamp": _utc_now(),
            "type": event_type,
            "iteration": iteration,
            "payload": _json_safe(payload),
        }

        self.events.append(event)

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    event,
                    ensure_ascii=False,
                )
                + "\n"
            )

    def close(
        self,
        state: dict[str, Any],
    ) -> Path:
        """
        Record the final dictionary-based AgentState.

        AgentState in this project is a TypedDict/dict,
        so dictionary access must be used here.
        """

        tool_calls = state.get(
            "tool_calls",
            [],
        )

        final_payload = {
            "goal": state.get("goal"),

            "terminated": state.get(
                "terminated",
                False,
            ),

            "termination_reason": state.get(
                "termination_reason"
            ),

            "incident_status": state.get(
                "incident_status"
            ),

            "total_iterations": state.get(
                "iteration",
                0,
            ),

            "max_iterations": state.get(
                "max_iterations"
            ),

            "tool_calls": tool_calls,

            "hypotheses": state.get(
                "hypotheses",
                [],
            ),

            "evidence": state.get(
                "evidence",
                [],
            ),

            "reflection_notes": state.get(
                "reflection_notes",
                [],
            ),

            "pending_approval": state.get(
                "pending_approval"
            ),

            "controller_grounded": state.get(
                "controller_grounded",
                False,
            ),

            "report": state.get(
                "report"
            ),
        }

        self.log(
            "final_state",
            final_payload,
            iteration=state.get(
                "iteration",
                0,
            ),
        )

        return self.path