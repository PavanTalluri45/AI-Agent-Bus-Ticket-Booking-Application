"""
Live step events for the bus-booking agent.

The agent nodes call ``begin_step`` / ``end_step`` / ``emit_done`` to report
what they are doing. Events are delivered to whatever emitter the current
request installed with ``set_step_emitter`` (the FastAPI streaming endpoints
do this). When no emitter is installed every call is a no-op, so the agent
still works exactly as before when it is run directly or from tests.

Rules for what goes into an event:

- Only short, human-readable text. Never database IDs, Razorpay IDs,
  passenger details or raw tool arguments/results.
- The full technical detail still goes to the terminal with ``print()``.
"""

import time
from contextvars import ContextVar, Token
from typing import Any, Callable, Literal
from uuid import uuid4

StepStatus = Literal["running", "done", "error"]
StepEmitter = Callable[[dict[str, Any]], None]


class _StepTracker:
    """Per-request state: the emitter plus the steps that are still open."""

    def __init__(self, emitter: StepEmitter) -> None:
        self.emitter = emitter
        # step_id -> (started_at, last_title)
        self.open_steps: dict[str, tuple[float, str]] = {}


_tracker: ContextVar[_StepTracker | None] = ContextVar(
    "bus_agent_step_tracker",
    default=None,
)


def set_step_emitter(emitter: StepEmitter) -> Token:
    """Install an emitter for the current context. Returns a reset token."""

    return _tracker.set(_StepTracker(emitter))


def reset_step_emitter(token: Token) -> None:
    _tracker.reset(token)


def _send(
    tracker: _StepTracker,
    step_id: str,
    title: str,
    status: StepStatus,
    description: str | None,
    duration_ms: int | None,
) -> None:
    event: dict[str, Any] = {
        "id": step_id,
        "title": title,
        "status": status,
    }

    if description:
        event["description"] = description

    if duration_ms is not None:
        event["duration_ms"] = duration_ms

    try:
        tracker.emitter(event)
    except Exception as exc:  # A UI event must never break the agent.
        print(f"[STEP EVENT] Failed to emit step: {exc}")


def begin_step(title: str, description: str | None = None) -> str:
    """Report a step that has started. Returns its ID for ``end_step``."""

    step_id = uuid4().hex[:10]
    tracker = _tracker.get()

    if tracker is not None:
        tracker.open_steps[step_id] = (time.perf_counter(), title)
        _send(tracker, step_id, title, "running", description, None)

    return step_id


def end_step(
    step_id: str,
    title: str | None = None,
    description: str | None = None,
    status: StepStatus = "done",
) -> None:
    """Finish a step started with ``begin_step`` (optionally retitling it)."""

    tracker = _tracker.get()

    if tracker is None:
        return

    started_at, last_title = tracker.open_steps.pop(
        step_id,
        (time.perf_counter(), title or ""),
    )

    _send(
        tracker,
        step_id,
        title or last_title,
        status,
        description,
        int((time.perf_counter() - started_at) * 1000),
    )


def emit_done(
    title: str,
    description: str | None = None,
    duration_ms: int | None = None,
    status: StepStatus = "done",
) -> None:
    """Report a step that is already finished (no running state)."""

    tracker = _tracker.get()

    if tracker is not None:
        _send(tracker, uuid4().hex[:10], title, status, description, duration_ms)


def close_open_steps(status: StepStatus = "error") -> None:
    """
    Close every step that never finished.

    A step stays open when the code between ``begin_step`` and ``end_step``
    raised and the node handled the exception itself.
    """

    tracker = _tracker.get()

    if tracker is None:
        return

    for step_id in list(tracker.open_steps):
        _, last_title = tracker.open_steps[step_id]
        end_step(step_id, f"{last_title} failed", status=status)
